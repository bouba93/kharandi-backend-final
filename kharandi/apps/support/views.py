from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Ticket, TicketMessage
from .serializers import TicketSerializer, TicketMessageSerializer

class TicketListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_staff or user.role == "admin":
            qs = Ticket.objects.all().select_related("user","agent")
        else:
            qs = Ticket.objects.filter(user=user)
        # Filtre par statut
        s = request.query_params.get("status")
        if s: qs = qs.filter(status=s)
        data = list(qs.values("id","ticket_number","subject","category","priority","status","created_at"))
        return Response({"success": True, "data": data})

    def post(self, request):
        s = TicketSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ticket = s.save(user=request.user)
        # Auto-priorité paiement
        if ticket.category == Ticket.Category.PAYMENT:
            ticket.priority = Ticket.Priority.HIGH
            ticket.save(update_fields=["priority"])
        return Response({"success": True, "message": "Ticket créé.", "data": TicketSerializer(ticket).data}, status=201)

class TicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_ticket(self, pk, user):
        try:
            if user.is_staff or user.role == "admin":
                return Ticket.objects.get(pk=pk)
            return Ticket.objects.get(pk=pk, user=user)
        except Ticket.DoesNotExist:
            return None

    def get(self, request, pk):
        ticket = self._get_ticket(pk, request.user)
        if not ticket:
            return Response({"success": False, "message": "Ticket introuvable."}, status=404)
        is_agent = request.user.is_staff or request.user.role == "admin"
        messages = ticket.messages.filter(
            is_internal=False  # Client ne voit pas les notes internes
        ) if not is_agent else ticket.messages.all()
        return Response({
            "success": True,
            "data": {
                **TicketSerializer(ticket).data,
                "messages": TicketMessageSerializer(messages, many=True).data,
            }
        })

    def post(self, request, pk):
        """Ajouter un message au ticket."""
        ticket = self._get_ticket(pk, request.user)
        if not ticket:
            return Response({"success": False, "message": "Ticket introuvable."}, status=404)
        is_agent  = request.user.is_staff or request.user.role == "admin"
        is_internal = bool(request.data.get("is_internal", False)) and is_agent
        msg = TicketMessage.objects.create(
            ticket=ticket,
            author=request.user,
            content=request.data.get("content", "").strip(),
            is_internal=is_internal,
        )
        return Response({"success": True, "data": TicketMessageSerializer(msg).data}, status=201)

class TicketResolveView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if not (request.user.is_staff or request.user.role == "admin"):
            return Response({"success": False, "message": "Réservé aux admins."}, status=403)
        try:
            ticket = Ticket.objects.get(pk=pk)
            ticket.resolve()
            return Response({"success": True, "message": f"Ticket #{ticket.ticket_number} résolu."})
        except Ticket.DoesNotExist:
            return Response({"success": False, "message": "Ticket introuvable."}, status=404)

class TicketAssignView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if not (request.user.is_staff or request.user.role == "admin"):
            return Response({"success": False, "message": "Réservé aux admins."}, status=403)
        try:
            ticket = Ticket.objects.get(pk=pk)
            ticket.assign_to(request.user)
            return Response({"success": True, "message": f"Ticket #{ticket.ticket_number} assigné."})
        except Ticket.DoesNotExist:
            return Response({"success": False, "message": "Ticket introuvable."}, status=404)
