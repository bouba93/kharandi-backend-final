from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Course, Enrollment, Grade
from .serializers import CourseListSerializer, CourseDetailSerializer, CourseCreateSerializer, EnrollmentSerializer, GradeSerializer

class CourseListCreateView(generics.ListCreateAPIView):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ["title","subject","description","tags","tutor__city"]
    ordering_fields  = ["price","avg_rating","students_count","created_at"]
    filterset_fields = ["level","subject","is_free"]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        return Course.objects.filter(status="active").select_related("tutor")

    def get_serializer_class(self):
        return CourseCreateSerializer if self.request.method == "POST" else CourseListSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != "tutor":
            return Response({"success": False, "message": "Seuls les répétiteurs peuvent créer des cours."}, status=403)
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"success": True, "message": "Cours soumis pour validation.", "data": s.data}, status=201)

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response({"success": True, "data": self.get_serializer(qs, many=True).data})

class CourseDetailView(generics.RetrieveUpdateAPIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]
    def get_queryset(self):
        return Course.objects.all().select_related("tutor")
    def get_serializer_class(self):
        return CourseCreateSerializer if self.request.method in ["PUT","PATCH"] else CourseDetailSerializer
    def retrieve(self, request, *args, **kwargs):
        return Response({"success": True, "data": CourseDetailSerializer(self.get_object(), context={"request":request}).data})

class EnrollmentView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        try:
            course = Course.objects.get(pk=pk, status="active")
        except Course.DoesNotExist:
            return Response({"success": False, "message": "Cours introuvable."}, status=404)
        if not course.is_free and float(course.price) > 0:
            return Response({"success": False, "message": "Ce cours est payant. Procédez au paiement d'abord."}, status=402)
        enr, created = Enrollment.objects.get_or_create(student=request.user, course=course)
        if not created:
            return Response({"success": False, "message": "Déjà inscrit à ce cours."}, status=400)
        return Response({"success": True, "message": f"Inscrit à '{course.title}'.", "data": EnrollmentSerializer(enr).data}, status=201)

class MyCoursesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = EnrollmentSerializer
    def get_queryset(self):
        return Enrollment.objects.filter(student=self.request.user, status="active").select_related("course__tutor")
    def list(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_queryset(), many=True).data})

class MyCoursesAsTutorView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = CourseListSerializer
    def get_queryset(self):
        return Course.objects.filter(tutor=self.request.user).order_by("-created_at")
    def list(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_queryset(), many=True).data})

class GradeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = GradeSerializer
    def get_queryset(self):
        return Grade.objects.filter(student=self.request.user).select_related("course")
    def list(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_queryset(), many=True).data})

class ProgressUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request, pk):
        try:
            enr = Enrollment.objects.get(pk=pk, student=request.user)
        except Enrollment.DoesNotExist:
            return Response({"success": False, "message": "Inscription introuvable."}, status=404)
        progress = min(100, max(0, int(request.data.get("progress", enr.progress))))
        enr.progress = progress
        if progress == 100:
            from django.utils import timezone
            enr.status       = Enrollment.Status.COMPLETED
            enr.completed_at = timezone.now()
        enr.save(update_fields=["progress", "status", "completed_at", "last_activity"])
        return Response({"success": True, "data": {"progress": progress, "status": enr.status}})
