from django.urls import path
from .views import CourseListCreateView, CourseDetailView, EnrollmentView, MyCoursesView, MyCoursesAsTutorView, GradeListView, ProgressUpdateView
urlpatterns = [
    path("",                        CourseListCreateView.as_view(),   name="course-list"),
    path("<int:pk>/",               CourseDetailView.as_view(),       name="course-detail"),
    path("<int:pk>/enroll/",        EnrollmentView.as_view(),         name="course-enroll"),
    path("my-courses/",             MyCoursesView.as_view(),          name="my-courses"),
    path("my-courses/as-tutor/",    MyCoursesAsTutorView.as_view(),   name="my-courses-tutor"),
    path("grades/",                 GradeListView.as_view(),          name="grades"),
    path("enrollment/<int:pk>/progress/", ProgressUpdateView.as_view(), name="progress-update"),
]
