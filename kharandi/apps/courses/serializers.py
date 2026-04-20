from rest_framework import serializers
from .models import Course, Enrollment, Grade

class CourseListSerializer(serializers.ModelSerializer):
    tutor_name = serializers.SerializerMethodField()
    tutor_city = serializers.CharField(source="tutor.city", read_only=True)
    class Meta:
        model  = Course
        fields = ["id","title","slug","subject","level","price","is_free",
                  "avg_rating","students_count","duration_hours","tutor_name","tutor_city","status"]
    def get_tutor_name(self, obj): return obj.tutor.get_full_name()

class CourseDetailSerializer(CourseListSerializer):
    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ["description","tags","cover_image","max_students","reviews_count","created_at"]

class CourseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Course
        fields = ["title","description","subject","level","price","is_free","tags","cover_image","duration_hours","max_students"]
    def create(self, validated_data):
        validated_data["tutor"] = self.context["request"].user
        return super().create(validated_data)

class EnrollmentSerializer(serializers.ModelSerializer):
    course_title   = serializers.CharField(source="course.title", read_only=True)
    course_subject = serializers.CharField(source="course.subject", read_only=True)
    tutor_name     = serializers.SerializerMethodField()
    class Meta:
        model  = Enrollment
        fields = ["id","course","course_title","course_subject","tutor_name","status","progress","enrolled_at"]
    def get_tutor_name(self, obj): return obj.course.tutor.get_full_name()

class GradeSerializer(serializers.ModelSerializer):
    course_subject = serializers.CharField(source="course.subject", read_only=True)
    course_title   = serializers.CharField(source="course.title", read_only=True)
    class Meta:
        model  = Grade
        fields = ["id","course","course_title","course_subject","score","max_score","grade_letter","graded_at"]
