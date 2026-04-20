import hashlib, logging
from django.conf import settings
from django.core.cache import cache
from django.db import models as db_models
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from .models import AIConversation, AIMessage, AIUsageLog

logger = logging.getLogger("kharandi")


class QuotaExceededException(Exception):
    pass


class AIThrottle(UserRateThrottle):
    scope = "ai"


class AIService:
    SYSTEM_PROMPT = (
        "Tu es Karamö, l'assistant éducatif intelligent de Kharandi — "
        "la plateforme scolaire numéro 1 en Guinée. "
        "Tu aides les élèves guinéens avec leurs cours, devoirs et questions scolaires. "
        "Réponds en français, de façon claire, pédagogique et encourageante. "
        "Adapte ton niveau au contexte scolaire (primaire, collège, lycée, université). "
        "Pour les matières scientifiques, montre toujours les étapes de résolution détaillées."
    )

    @classmethod
    def get_daily_limit(cls, user):
        return settings.AI_DAILY_LIMIT_FREE

    @classmethod
    def get_daily_usage(cls, user):
        return cache.get(f"ai_q_{user.id}_{timezone.now().date()}", 0)

    @classmethod
    def increment_usage(cls, user):
        key = f"ai_q_{user.id}_{timezone.now().date()}"
        current = cache.get(key, 0)
        cache.set(key, current + 1, timeout=26 * 3600)

    @classmethod
    def get_cache_key(cls, question, subject):
        return f"ai_resp_{hashlib.md5(f'{subject.lower()}:{question.lower().strip()}'.encode()).hexdigest()}"

    @classmethod
    def ask(cls, user, question, subject="", history=None):
        limit = cls.get_daily_limit(user)
        used  = cls.get_daily_usage(user)
        if used >= limit:
            raise QuotaExceededException(
                f"Quota journalier atteint ({limit} questions/jour). Revenez demain ou passez à Premium."
            )
        ck = cls.get_cache_key(question, subject)
        cached = cache.get(ck)
        if cached:
            cls.increment_usage(user)
            cls._log(user, 0)
            return {"answer": cached, "tokens_used": 0, "was_cached": True, "remaining_quota": limit - used - 1}

        q_full = f"[Matière: {subject}]\n\n{question}" if subject else question
        msgs   = list((history or [])[-10:]) + [{"role": "user", "content": q_full}]
        answer, tokens = cls._call(settings.AI_PROVIDER, msgs)
        cache.set(ck, answer, timeout=settings.AI_CACHE_TIMEOUT)
        cls.increment_usage(user)
        cls._log(user, tokens)
        return {"answer": answer, "tokens_used": tokens, "was_cached": False, "remaining_quota": limit - used - 1}

    @classmethod
    def _log(cls, user, tokens):
        obj, _ = AIUsageLog.objects.get_or_create(user=user, date=timezone.now().date())
        AIUsageLog.objects.filter(pk=obj.pk).update(
            questions=db_models.F("questions") + 1, tokens=db_models.F("tokens") + tokens
        )

    @classmethod
    def _call(cls, provider, messages):
        import requests as req
        if provider == "gemini":
            url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
            cont = [{"role": "user" if m["role"]=="user" else "model", "parts":[{"text":m["content"]}]} for m in messages]
            r    = req.post(url, json={"system_instruction":{"parts":[{"text":cls.SYSTEM_PROMPT}]},"contents":cont,"generationConfig":{"maxOutputTokens":1500,"temperature":0.7}}, timeout=30)
            r.raise_for_status()
            d = r.json()
            return d["candidates"][0]["content"]["parts"][0]["text"], d.get("usageMetadata",{}).get("totalTokenCount",0)
        elif provider == "deepseek":
            r = req.post("https://api.deepseek.com/chat/completions",
                json={"model":"deepseek-chat","messages":[{"role":"system","content":cls.SYSTEM_PROMPT}]+messages,"max_tokens":1500},
                headers={"Authorization":f"Bearer {settings.DEEPSEEK_API_KEY}","Content-Type":"application/json"}, timeout=30)
            r.raise_for_status()
            d = r.json()
            return d["choices"][0]["message"]["content"], d.get("usage",{}).get("total_tokens",0)
        elif provider == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp   = client.messages.create(model="claude-opus-4-6", max_tokens=1500, system=cls.SYSTEM_PROMPT, messages=messages)
            return resp.content[0].text, resp.usage.input_tokens + resp.usage.output_tokens
        raise ValueError(f"Provider inconnu: {provider}")


class KaramoAskView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [AIThrottle]

    def post(self, request):
        question = request.data.get("question", "").strip()
        subject  = request.data.get("subject", "").strip()
        conv_id  = request.data.get("conversation_id")
        if len(question) < 5:
            return Response({"success": False, "message": "Question trop courte (min 5 chars)."}, status=400)
        if len(question) > 3000:
            return Response({"success": False, "message": "Question trop longue (max 3000 chars)."}, status=400)
        if conv_id:
            try: conv = AIConversation.objects.get(id=conv_id, user=request.user)
            except AIConversation.DoesNotExist: return Response({"success":False,"message":"Conversation introuvable."},status=404)
        else:
            conv = AIConversation.objects.create(user=request.user, subject=subject, title=question[:80])
        history = list(conv.messages.order_by("-created_at")[:10].values("role","content"))
        history.reverse()
        try:
            result = AIService.ask(user=request.user, question=question, subject=subject, history=history)
        except QuotaExceededException as e:
            return Response({"success":False,"message":str(e),"quota_exceeded":True}, status=429)
        except Exception as e:
            logger.exception(e)
            return Response({"success":False,"message":"Service IA indisponible."}, status=503)
        AIMessage.objects.create(conversation=conv, role=AIMessage.Role.USER, content=question)
        AIMessage.objects.create(conversation=conv, role=AIMessage.Role.ASSISTANT,
            content=result["answer"], tokens_used=result["tokens_used"], was_cached=result["was_cached"])
        AIConversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())
        return Response({"success":True,"data":{**result,"conversation_id":conv.id}})


class KaramoQuotaView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        limit = AIService.get_daily_limit(request.user)
        used  = AIService.get_daily_usage(request.user)
        return Response({"success":True,"data":{"daily_limit":limit,"daily_used":used,"daily_remaining":max(0,limit-used)}})


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        convs = AIConversation.objects.filter(user=request.user, is_active=True).order_by("-updated_at")[:20]
        return Response({"success":True,"data":[{"id":c.id,"title":c.title,"subject":c.subject,"updated_at":c.updated_at.isoformat()} for c in convs]})


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, conversation_id):
        try: conv = AIConversation.objects.get(id=conversation_id, user=request.user)
        except AIConversation.DoesNotExist: return Response({"success":False,"message":"Introuvable."},status=404)
        msgs = list(conv.messages.order_by("created_at").values("id","role","content","was_cached","created_at"))
        return Response({"success":True,"data":{"conversation":{"id":conv.id,"title":conv.title,"subject":conv.subject},"messages":msgs}})
    def delete(self, request, conversation_id):
        try:
            conv = AIConversation.objects.get(id=conversation_id, user=request.user)
            conv.is_active = False
            conv.save(update_fields=["is_active"])
            return Response({"success":True,"message":"Conversation archivée."})
        except AIConversation.DoesNotExist:
            return Response({"success":False,"message":"Introuvable."},status=404)
