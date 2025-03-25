from django.urls import path, include
from django.contrib import admin
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.http import HttpResponseRedirect
from rest_framework import permissions
from core.views import (
    CourseViewSet, ModuleViewSet, QuizViewSet, LearningPathViewSet, 
    RegisterView, LoginView, VerifyEmailView, PasswordResetRequestView,
    PasswordResetConfirmView, ModuleProgressViewSet, QuizProgressViewSet,
    CourseProgressViewSet, get_user_profile, update_course_progress, get_module_by_name, submit_quiz, LearningPathProgressViewSet, get_module_progress, get_next_learning_path, generate_quiz_from_video, generate_learning_paths
)

# Versioned Router Setup for API
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'learning-paths', LearningPathViewSet, basename='learning_path')
router.register(r'module-progress', ModuleProgressViewSet, basename='moduleprogress')
router.register(r'quiz-progress', QuizProgressViewSet, basename='quizprogress')
router.register(r'course-progress', CourseProgressViewSet, basename='course-progress')
router.register(r'learning-path-progress', LearningPathProgressViewSet, basename='learning-path-progress')

# Swagger schema view
schema_view = get_schema_view(
    openapi.Info(
        title="Learning Platform API",
        default_version='v1',
        description="API documentation for the Learning Platform",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls), 
    path('', lambda request: HttpResponseRedirect('/api/v1/')),  # Redirect to API base URL
    # Register and Login endpoints
    path('api/v1/register/', RegisterView.as_view(), name='register_v1'),
    path('api/v1/login/', LoginView.as_view(), name='login_v1'),
    # JWT Token endpoints
    path('api/v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair_v1'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh_v1'),
    path('api/v1/verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('api/v1/password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('api/v1/reset-password-confirm/', PasswordResetConfirmView.as_view(), name='reset_password_confirm'),
    path('api/v1/user-profile/', get_user_profile, name='get_user_profile'),  # Fetch user profile
    path('api/v1/course-progress/<int:course_id>/', CourseProgressViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}), name='course-progress-detail'), 
    # Explicit path for retrieving module details
    path('api/v1/modules/<int:pk>/', ModuleViewSet.as_view({'get': 'retrieve'}), name='module-detail'),  
    path('api/v1/module-by-name/<str:module_name>/', get_module_by_name, name='get_module_by_name'),
    path('api/v1/quizzes/<int:quiz_id>/submit/', submit_quiz, name='submit_quiz'),
    path('api/v1/module-progress', get_module_progress, name='get_module_progress'),
    path('api/v1/next-learning-path/<int:current_learning_path_id>/', get_next_learning_path, name='get_next_learning_path'),
    path("generate-learning-paths/", generate_learning_paths, name="generate_learning_paths"),
    # Versioned router endpoint
    path('api/v1/', include(router.urls)),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
