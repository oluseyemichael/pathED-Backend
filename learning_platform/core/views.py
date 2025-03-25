from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from .models import Course, LearningPath, Module, Quiz, Question, Answer, ModuleProgress, QuizProgress, CourseProgress, LearningPathProgress
from .serializers import CourseSerializer, LearningPathSerializer, ModuleSerializer, QuizSerializer, UserSerializer, ModuleProgressSerializer, QuizProgressSerializer, CourseProgressSerializer, LearningPathProgressSerializer
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import action,  api_view, permission_classes
from rest_framework import status
from django.utils import timezone
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from .services.quiz_generation_service import (
    fetch_video_transcript, fetch_video_description, generate_quiz_with_chat_api, generate_default_quiz, generate_quiz_from_module
)
import os
import json
import google.generativeai as genai
import logging
logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

User = get_user_model()  # This will import the custom User model

class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                user.is_active = False  # Mark user as inactive until they verify their email
                user.save()

                # Generate email verification token
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)

                # Construct the verification link
                verification_link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
                send_mail(
                    'Verify Your Account',
                    f'Hi, Welcome to pathED. Please click the following link to verify your account: {verification_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email]
                )

                return Response({
                    'message': 'Registration successful. Check your email to verify your account.',
                    'user': {
                        'username': user.username,
                        'email': user.email,
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    'error': 'Registration failed',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyEmailView(APIView):
    def get(self, request):
        uid = request.GET.get('uid')
        token = request.GET.get('token')
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user and token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({'message': 'Email verified successfully.'})
        
        return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        # # Try to find user by email
        # try:
        #     user = User.objects.get(email=email)
        #     username = user.username
        # except User.DoesNotExist:
        #     return Response({
        #         'error': 'No account found with this email'
        #     }, status=status.HTTP_404_NOT_FOUND)
        
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if user:
            if not user.is_active:
                return Response({
                    'error': 'Please verify your email to activate your account.'
                }, status=status.HTTP_403_FORBIDDEN)
                
            refresh = RefreshToken.for_user(user)
            return Response({
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                },
                'user': {
                    'username': user.username,
                    'email': user.email,
                }
            })
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

class PasswordResetRequestView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{request.build_absolute_uri('/api/v1/reset-password-confirm/')}?uid={uid}&token={token}"
            
            send_mail(
                subject="Reset Your Password",
                message=f"Click the link to reset your password: {reset_url}",
                from_email="pathed.001@gmail.com",
                recipient_list=[user.email],
            )
            return Response({'message': 'Password reset email sent.'})
        except User.DoesNotExist:
            return Response({'error': 'User with this email does not exist.'}, status=status.HTTP_404_NOT_FOUND)

class PasswordResetConfirmView(APIView):
    def post(self, request):
        uid = request.GET.get('uid')
        token = request.GET.get('token')
        new_password = request.data.get('new_password')
        
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid link'}, status=status.HTTP_400_BAD_REQUEST)
        
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({'message': 'Password reset successful'})
        return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

# Course ViewSet
class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]  # Protecting this route

# Learning Path ViewSet
class LearningPathViewSet(viewsets.ModelViewSet):
    queryset = LearningPath.objects.all()
    serializer_class = LearningPathSerializer
    permission_classes = [IsAuthenticated]

# Module ViewSet
class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]

# Quiz ViewSet
class QuizViewSet(viewsets.ModelViewSet):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated]

# Module Progress ViewSet
class ModuleProgressViewSet(viewsets.ModelViewSet):
    queryset = ModuleProgress.objects.all()
    serializer_class = ModuleProgressSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['patch'], url_path='update-progress')
    def update_progress(self, request, pk=None):
        user = request.user
        module = Module.objects.get(pk=pk)
        
        # Use `update_or_create` to ensure progress exists
        progress, created = ModuleProgress.objects.update_or_create(
            user=user,
            module=module,
            defaults=request.data  # Pass data to update fields
        )

        return Response(
            ModuleProgressSerializer(progress).data,
            status=status.HTTP_200_OK
        )

# Quiz Progress ViewSet
class QuizProgressViewSet(viewsets.ModelViewSet):
    queryset = QuizProgress.objects.all()
    serializer_class = QuizProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.request.query_params.get('user')
        if user_id:
            return self.queryset.filter(user_id=user_id)
        return self.queryset
    
class LearningPathProgressViewSet(viewsets.ModelViewSet):
    queryset = LearningPathProgress.objects.all()
    serializer_class = LearningPathProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(user=user)

    def retrieve(self, request, pk=None):
        try:
            # Get the learning path instance
            learning_path = LearningPath.objects.get(pk=pk)
        except LearningPath.DoesNotExist:
            return Response(
                {"detail": "Learning path not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if progress exists
        progress, created = LearningPathProgress.objects.get_or_create(
            user=request.user, 
            learning_path=learning_path,
            defaults={"progress_percentage": 0.0, "completed": False}
        )

        serializer = self.get_serializer(progress)
        return Response(serializer.data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)

    
# Course Progress ViewSet
class CourseProgressViewSet(viewsets.ModelViewSet):
    queryset = CourseProgress.objects.all()
    serializer_class = CourseProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Limit the queryset to the logged-in user's data
        user = self.request.user
        return self.queryset.filter(user=user)

    def retrieve(self, request, course_id=None):
        """
        Retrieve progress for a specific course by ID.
        """
        try:
            # Use course_id instead of pk
            course_progress = self.get_queryset().get(course=course_id)
            course_progress.calculate_progress()  # Update progress if needed
            return Response(CourseProgressSerializer(course_progress).data)
        except CourseProgress.DoesNotExist:
            return Response({"error": "Course progress not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error fetching course progress: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """Fetch user profile data including course progress."""
    user = request.user
    user_data = {
        "username": user.username,
        "email": user.email,
    }

    # Fetch course progress data for the user
    progress_data = CourseProgress.objects.filter(user=user)
    progress_serialized = CourseProgressSerializer(progress_data, many=True).data

    user_data["progress_data"] = progress_serialized
    return Response(user_data)



@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_course_progress(request, course_id):
    user = request.user
    progress_percentage = request.data.get("progress_percentage", 0)

    # Update or create course progress for this user and course
    progress, created = CourseProgress.objects.update_or_create(
        user=user,
        course_id=course_id,
        defaults={"progress_percentage": progress_percentage}
    )

    # Recalculate and update progress status
    progress.calculate_progress()

    return Response({"message": "Progress updated successfully", "progress": CourseProgressSerializer(progress).data})

@api_view(['GET'])
def get_module_by_name(request, module_name):
    try:
         # Prefetch quizzes and their related questions and answers
        module = Module.objects.prefetch_related(
            Prefetch(
                'quizzes',
                queryset=Quiz.objects.prefetch_related('questions__answers')
            )
        ).get(module_name=module_name)
        serializer = ModuleSerializer(module)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Module.DoesNotExist:
        return Response({'error': 'Module not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching module: {str(e)}")
        return Response({'error': 'An unexpected error occurred'}, status=500)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_module_progress(request, module_id):
    try:
        module_progress, created = ModuleProgress.objects.update_or_create(
            user=request.user, module_id=module_id,
            defaults={'video_watched': True}
        )
        module_progress.calculate_progress()
        return Response(ModuleProgressSerializer(module_progress).data)
    except Module.DoesNotExist:
        return Response({"error": "Module not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_module_progress(request):
    """
    Retrieve module progress for the logged-in user for a specific learning path.
    """
    learning_path_id = request.query_params.get('learning_path')  # Get learning path ID from query params
    print(f"[DEBUG] Received learning_path_id: {learning_path_id}")
    print(f"[DEBUG] Authenticated User: {request.user}")

    if not learning_path_id:
        print("[DEBUG] Missing learning_path_id")
        return Response({"detail": "Learning path ID is required"}, status=400)

    progress = ModuleProgress.objects.filter(
        user=request.user, 
        module__learning_path_id=learning_path_id
    ).values(
        "module__module_name",
        "completed",
        "completion_date",
        "video_watched",
        "quiz_completed"
    )

    print(f"[DEBUG] Module Progress Data for {request.user}: {progress}")
    return Response(list(progress), status=200)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_quiz_score(request, quiz_id):
    score = request.data.get("score", 0)
    try:
        quiz_progress, created = QuizProgress.objects.update_or_create(
            user=request.user, quiz_id=quiz_id,
            defaults={'score': score}
        )
        quiz_progress.calculate_progress()
        return Response(QuizProgressSerializer(quiz_progress).data)
    except Quiz.DoesNotExist:
        return Response({"error": "Quiz not found"}, status=status.HTTP_404_NOT_FOUND)


    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, quiz_id):
    try:
        user = request.user
        quiz = Quiz.objects.get(id=quiz_id)

        # Log incoming request
        print(f"User: {user}, Quiz ID: {quiz_id}, Request Data: {request.data}")

        answers = request.data.get('answers', [])
        total_questions = quiz.questions.count()
        correct_answers = 0

        # Check and calculate correct answers
        for answer in answers:
            question_id = answer.get('question_id')
            answer_id = answer.get('answer_id')

            print(f"Checking Question ID: {question_id}, Answer ID: {answer_id}")

            if Answer.objects.filter(
                id=answer_id,
                question_id=question_id,
                is_correct=True
            ).exists():
                correct_answers += 1

        # Calculate the score
        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        print(f"Correct Answers: {correct_answers}, Score: {score}")

        # Update or create QuizProgress without triggering infinite recursion
        quiz_progress, _ = QuizProgress.objects.update_or_create(
            user=user,
            quiz=quiz,
            defaults={
                "score": score,
                "completed": score >= 70.0,
                "completion_date": timezone.now() if score >= 70.0 else None
            },
        )

        print(f"QuizProgress Updated: {quiz_progress}")

        # Avoid recursion in `CourseProgress` by calculating explicitly
        course_progress = CourseProgress.objects.filter(user=user, course=quiz.module.learning_path.course).first()
        if course_progress:
            course_progress.calculate_progress()

        return Response({"score": score, "completed": quiz_progress.completed})

    except Quiz.DoesNotExist:
        return Response({"error": "Quiz not found"}, status=404)
    except Exception as e:
        print(f"Error in submit_quiz: {e}")
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_learning_path(request, current_learning_path_id):
    try:
        current_path = LearningPath.objects.get(id=current_learning_path_id)
        next_path = LearningPath.objects.filter(
            course=current_path.course,
            id__gt=current_path.id  # Assuming IDs represent order
        ).order_by('id').first()

        if next_path:
            serializer = LearningPathSerializer(next_path)
            return Response(serializer.data, status=200)
        else:
            return Response({"detail": "No more learning paths available"}, status=404)
    except LearningPath.DoesNotExist:
        return Response({"error": "Current learning path not found"}, status=404)
    


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_quiz_from_video(request, module_id):
    """
    Generate a quiz for a module using the associated YouTube video.
    """
    try:
        module = Module.objects.get(id=module_id)

        # Try to fetch transcript
        content = fetch_video_transcript(module.video_link)
        if not content:
            # Fallback to fetching video description
            print(f"No transcript available for {module.video_link}, trying description...")
            content = fetch_video_description(module.video_link)

        if not content:
            # Dynamically generate meaningful fallback content
            print(f"No transcript or description available for {module.video_link}. Generating default content.")
            content = f"This module covers the topic: {module.topic}. Please prepare questions related to {module.topic}."

        # Generate quiz questions
        questions_text = generate_quiz_with_chat_api(content)
        if not questions_text:
            # Generate quiz from default OpenAI fallback
            print(f"Failed to generate quiz from content. Using default OpenAI generation.")
            questions_text = generate_default_quiz(module.topic)

        if not questions_text:
            return Response({"error": "Failed to generate quiz questions."}, status=500)

        # Save quiz and questions to database
        quiz = Quiz.objects.create(quiz_name=f"Quiz for {module.module_name}", module=module)
        questions = questions_text.split("\n\n")

        for question_data in questions:
            if not question_data.strip():
                continue

            lines = question_data.split("\n")
            question_text = lines[0].strip()
            answers = lines[1:]

            question = Question.objects.create(quiz=quiz, question_text=question_text)
            for answer in answers:
                is_correct = "Correct:" in answer
                Answer.objects.create(
                    question=question,
                    answer_text=answer.replace("Correct:", "").strip(),
                    is_correct=is_correct,
                )

        return Response({"message": "Quiz generated successfully!", "quiz_id": quiz.id})
    except Module.DoesNotExist:
        return Response({"error": "Module not found"}, status=404)
    except Exception as e:
        print(f"Error generating quiz: {e}")
        return Response({"error": str(e)}, status=500)

@api_view(["POST"])
def generate_learning_paths(request):
    user_input = request.data.get("course_name", "").strip() # Get course name from user
    
    if not user_input:
        return Response({"error": "Course name is required."}, status=400)
    
    # Check if course already exists
    course, _ = Course.object.get_or_create(name=user_input)
    
    # AI Prompt
    model = genai.GenerativeModel("gemini-pro")
    prompt = (
        f"You are an expert educator designing structure learning paths for students."
        f"Generate multiple logical learning paths for {user_input}, each containing 5-8 modules."
        f"Output in structured JSON format with 'learning_paths as an array, each having 'path_name' and 'modules'."
    )
    
    try:
        response = model.generate_content(prompt)
        data = json.loads(response.text) # Parse AI response into JSON
        
        for path in data.get("learning_paths", []):
            learning_path, _ = LearningPath.objects.get_or_create(course=course, path_name=path["path_name"])
            
            for module_name in path["modules"]:
                Module.objects.get_or_create(learning_path=learning_path, module_name=module_name)
                
        return Response({"message": "Learning paths generated successfully!", "learning_paths": data["learning_paths"]}, status=201)

    except Exception as e:
        return Response({"error": str(e)}, status=500)