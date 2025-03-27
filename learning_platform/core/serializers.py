from rest_framework import serializers
from django.contrib.auth.models import User
from .models import User, Course, LearningPath, Module, Quiz, Answer, Question, ModuleProgress, QuizProgress, CourseProgress, LearningPathProgress

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'full_name')
        extra_kwargs = {
            'password': {'write_only': True},  # Password should not be readable
            'email': {'required': True, 'allow_blank': False},  # Ensure email is required and not blank
            'full_name': {'required': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            full_name=validated_data['full_name']
        )
        return user

class LearningPathSerializer(serializers.ModelSerializer):
    modules = serializers.StringRelatedField(many=True, source='modules.all')

    class Meta:
        model = LearningPath
        fields = ['id','path_name', 'modules']
        

class CourseSerializer(serializers.ModelSerializer):
    learning_paths = LearningPathSerializer(many=True)  #nested serializer here

    class Meta:
        model = Course
        fields = ['id', 'course_name', 'description', 'learning_paths']


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'is_correct']

class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'answers']

class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'quiz_name', 'questions']

class ModuleSerializer(serializers.ModelSerializer):
    quizzes = QuizSerializer(many=True, read_only=True)  # Include quiz data

    class Meta:
        model = Module
        fields = ['id', 'module_name', 'topic', 'video_link', 'blog_link', 'quizzes']

class ModuleProgressSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = ModuleProgress
        fields = ['user', 'module', 'completed', 'completion_date', 'video_watched', 'quiz_completed']

class QuizProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizProgress
        fields = ['user', 'quiz', 'score', 'completed', 'completion_date']

class LearningPathProgressSerializer(serializers.ModelSerializer):
    learning_path_name = serializers.SerializerMethodField()

    class Meta:
        model = LearningPathProgress
        fields = [
            'id', 
            'learning_path', 
            'learning_path_name', 
            'completed', 
            'completion_date', 
            'progress_percentage'
        ]

    def get_learning_path_name(self, obj):
        return obj.learning_path.path_name if obj.learning_path else None
        
class CourseProgressSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    course = serializers.StringRelatedField()
    learning_path_progress = serializers.SerializerMethodField()

    class Meta:
        model = CourseProgress
        fields = [
            'id',
            'user',
            'course',
            'completed',
            'completion_date',
            'progress_percentage',
            'learning_path_progress',
        ]
        
    def get_learning_path_progress(self, obj):
        """Fetch progress for all learning paths in this course."""
        learning_paths = obj.course.learning_paths.all()
        progress_data = LearningPathProgress.objects.filter(
            user=obj.user, learning_path__in=learning_paths
        )
        return LearningPathProgressSerializer(progress_data, many=True).data