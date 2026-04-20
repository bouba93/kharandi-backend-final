"""
╔══════════════════════════════════════════════════════════════════════════╗
║           KHARANDI — Paiements : Vues LengoPay                         ║
║  Appels synchrones (sans Celery) — génération facture PDF inline        ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import logging
import requests

from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status as http_status

from .models import Transaction, Commission, Invoice
from kharandi.services.sms import (
    send_sms, normalize_phone,
    sms_payment_success, sms_payment_failed,
)

logger = logging.getLogger("kharandi")


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount       = request.data.get("amount")
        currency     = request.data.get("currency", "GNF")
        order_id     = request.data.get("order_id")
        course_id    = request.data.get("course_id")
        return_url   = request.data.get("return_url", "")
        failure_url  = request.data.get("failure_url", "")
        callback_url = request.data.get(
            "callback_url",
            request.build_absolute_uri("/api/payments/callback/")
        )

        if not amount or float(amount) <= 0:
            return Response(
                {"success": False, "message": "'amount' requis et positif."},
                status=http_status.HTTP_400_BAD_REQUEST
            )

        amount_float = float(amount)
        rate         = settings.PLATFORM_COMMISSION_RATE
        comm_amount  = round(amount_float * rate, 2)
        net_amount   = round(amount_float - comm_amount, 2)

        payload = {
            "websiteid":    settings.LENGOPAY_WEBSITE_ID,
            "currency":     currency,
            "amount":       int(amount_float),
            "callback_url": callback_url,
        }
        if return_url:  payload["return_url"]  = return_url
        if failure_url: payload["failure_url"] = failure_url

        headers = {
            "Authorization": f"Basic {settings.LENGOPAY_LICENSE_KEY}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

        try:
            resp   = requests.post(settings.LENGOPAY_API_URL, json=payload,
                                   headers=headers, timeout=15)
            result = resp.json()

            if resp.status_code == 200 and result.get("status") == "Success":
                pay_id = result["pay_id"]

                # Déterminer le type
                txn_type = Transaction.Type.PRODUCT if order_id else Transaction.Type.COURSE

                # Créer la transaction PENDING
                txn = Transaction.objects.create(
                    payer=request.user,
                    amount=amount_float,
                    commission_rate=rate,
                    commission_amount=comm_amount,
                    net_amount=net_amount,
                    lengopay_id=pay_id,
                    transaction_type=txn_type,
                    status=Transaction.Status.PENDING,
                )

                # Lier à la commande si fournie
                if order_id:
                    from kharandi.apps.marketplace.models import Order
                    try:
                        order = Order.objects.get(pk=order_id, buyer=request.user)
                        txn.order = order
                        txn.save(update_fields=["order"])
                    except Order.DoesNotExist:
                        pass

                logger.info(f"💳 Paiement initié: {pay_id} — {amount} {currency}")
                return Response({
                    "success": True,
                    "message": "Session de paiement créée.",
                    "data": {
                        "pay_id":         pay_id,
                        "payment_url":    result["payment_url"],
                        "transaction_id": txn.id,
                    }
                })

            logger.error(f"LengoPay erreur: {result}")
            return Response(
                {"success": False, "message": f"Erreur LengoPay : {result}"},
                status=resp.status_code
            )

        except requests.exceptions.Timeout:
            return Response(
                {"success": False, "message": "Service de paiement indisponible (timeout)."},
                status=http_status.HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as e:
            logger.exception(e)
            return Response(
                {"success": False, "message": "Erreur interne."},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentCallbackView(APIView):
    """
    Webhook LengoPay — reçu après chaque transaction.
    Synchrone : valide en DB + SMS + génère facture PDF inline.
    LengoPay attend HTTP 200 pour confirmer la réception.
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        data       = request.data if request.data else {}
        pay_id     = data.get("pay_id")
        pay_status = data.get("status")
        amount     = int(data.get("amount", 0))
        client     = str(data.get("Client", ""))

        logger.info(f"[CALLBACK] pay_id={pay_id} | status={pay_status} | amount={amount}")

        if not pay_id or not pay_status:
            return Response({"error": "Données invalides"}, status=400)

        try:
            txn = Transaction.objects.select_for_update().get(lengopay_id=pay_id)
        except Transaction.DoesNotExist:
            logger.warning(f"Transaction inconnue: {pay_id}")
            return Response({"received": True}, status=200)

        if pay_status == "SUCCESS":
            txn.status          = Transaction.Status.SUCCESS
            txn.lengopay_payload = data
            txn.save(update_fields=["status", "lengopay_payload"])

            # Commission
            Commission.objects.get_or_create(
                transaction=txn,
                defaults={
                    "vendor":           txn.recipient or txn.payer,
                    "rate":             txn.commission_rate,
                    "gross_amount":     txn.amount,
                    "commission_amount": txn.commission_amount,
                    "net_amount":       txn.net_amount,
                }
            )

            # Marquer la commande payée
            if txn.order:
                txn.order.mark_as_paid(pay_id)

            # Générer facture PDF synchrone
            try:
                _generate_invoice(txn)
            except Exception as e:
                logger.error(f"Erreur génération facture {txn.id}: {e}")

            # SMS au client
            if client:
                phone = normalize_phone(client)
                send_sms(phone, sms_payment_success(amount))

            logger.info(f"✅ Paiement validé: {pay_id} — {amount} GNF")

        elif pay_status == "FAILED":
            txn.status         = Transaction.Status.FAILED
            txn.failure_reason = data.get("message", "")
            txn.save(update_fields=["status", "failure_reason"])

            if client:
                send_sms(normalize_phone(client), sms_payment_failed(amount))

            logger.warning(f"❌ Paiement échoué: {pay_id}")

        return Response({"received": True}, status=200)


def _generate_invoice(txn: Transaction):
    """Génère et sauvegarde la facture PDF d'une transaction réussie."""
    from kharandi.apps.reports.generators import generate_invoice_pdf_buffer
    from django.core.files.base import ContentFile

    invoice_number = f"KH-INV-{timezone.now().strftime('%Y%m')}-{txn.pk:06d}"
    invoice, created = Invoice.objects.get_or_create(
        transaction=txn,
        defaults={"invoice_number": invoice_number}
    )
    if created:
        buf = generate_invoice_pdf_buffer(txn)
        invoice.pdf_file.save(f"{invoice_number}.pdf", ContentFile(buf.getvalue()), save=True)
        logger.info(f"📄 Facture créée : {invoice_number}")


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        txns = Transaction.objects.filter(
            payer=request.user
        ).order_by("-created_at")[:50]

        data = list(txns.values(
            "id", "lengopay_id", "amount", "commission_amount",
            "net_amount", "status", "transaction_type", "created_at"
        ))
        return Response({"success": True, "data": data})


class InvoiceDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, transaction__payer=request.user)
        except Invoice.DoesNotExist:
            return Response({"success": False, "message": "Facture introuvable."}, status=404)

        if invoice.pdf_file:
            return FileResponse(
                invoice.pdf_file.open(),
                as_attachment=True,
                filename=f"{invoice.invoice_number}.pdf",
                content_type="application/pdf",
            )
        return Response({"success": False, "message": "PDF non encore généré."}, status=404)


class SMSBalanceView(APIView):
    """Vérifie le solde NimbaSMS — admin seulement."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_staff or request.user.role == "admin"):
            return Response({"success": False, "message": "Accès réservé aux admins."}, status=403)
        from kharandi.services.sms import get_sms_balance
        result = get_sms_balance()
        return Response({"success": result["success"], "data": result})
