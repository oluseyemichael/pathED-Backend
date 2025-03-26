from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model  # Import get_user_model
from .services.youtube_service import get_youtube_videos
from .services.blog_service import get_blog_posts
from django.core.validators import EmailValidator
from django.utils import timezone
from django.db.models import Q
import math
from functools import wraps
from django.db import DatabaseError
import time

def circuit_breaker(max_failures=3, timeout=60):
    def decorator(func):
        failures = 0
        last_failure = 0
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal failures, last_failure
            if failures >= max_failures and time.time() - last_failure < timeout:
                raise DatabaseError("Service temporarily unavailable")
            try:
                result = func(*args, **kwargs)
                failures = 0
                return result
            except Exception as e:
                failures += 1
                last_failure = time.time()
                raise
        return wrapper
    return decorator

# User model
class User(AbstractUser):
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        error_messages={
            'unique': "A user with that email already exists.",
        }
    )
    is_admin = models.BooleanField(default=False)
    
    # Use username as the primary identifier
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'full_name']


User = get_user_model()  # Assigning User model via get_user_model()

# Course model
class Course(models.Model):
    course_name = models.CharField(max_length=255)
    description = models.TextField()
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.course_name

# LearningPath model
class LearningPath(models.Model):
    path_name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, related_name='learning_paths', on_delete=models.CASCADE)
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.path_name

# Module model with auto-fetching for YouTube video and blog content
class Module(models.Model):
    module_name = models.CharField(max_length=255)
    learning_path = models.ForeignKey(LearningPath, related_name='modules', on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)
    video_link = models.CharField(max_length=500, blank=True)
    blog_link = models.CharField(max_length=500, blank=True)

    @circuit_breaker()
    def save(self, *args, **kwargs):
        # Fetch potential YouTube videos for the module topic
        youtube_videos = get_youtube_videos(self.topic)
        if youtube_videos:
            # Select the best video automatically
            self.video_link = youtube_videos[0]['url']
            
            # Log all potential videos for manual review
            print(f"Potential videos for '{self.topic}':")
            for video in youtube_videos:
                print(f"- {video['url']} ({video['title']})")
        else:
            print(f"No suitable videos found for topic '{self.topic}'.")

        # Fetch blog content
        blog_post = get_blog_posts(self.topic)
        if blog_post:
            self.blog_link = blog_post['url']

        super(Module, self).save(*args, **kwargs)

    def __str__(self):
        return self.module_name

# Quiz model
class Quiz(models.Model):
    quiz_name = models.CharField(max_length=255)
    module = models.ForeignKey(Module, related_name='quizzes', on_delete=models.CASCADE)
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.quiz_name

# Question model
class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE)
    question_text = models.TextField()

    def __str__(self):
        return self.question_text

# Answer model
class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text

# Progress Tracking Models
class ModuleProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="module_progress")
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    video_watched = models.BooleanField(default=False)
    quiz_completed = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)

    def calculate_progress(self):
        """Calculate module completion progress."""
        self.completed = self.video_watched and self.quiz_completed
        if self.completed:
            self.completion_date = timezone.now()
        else:
            self.completion_date = None

        # Update the database to avoid recursion
        ModuleProgress.objects.filter(pk=self.pk).update(
            completed=self.completed,
            completion_date=self.completion_date
        )
        print(f"[DEBUG] Module Progress Updated: {self.user.username} - {self.module.module_name} - Completed: {self.completed}")

        # Trigger learning path progress update
        learning_path_progress = LearningPathProgress.objects.filter(
            user=self.user, learning_path=self.module.learning_path
        ).first()
        if learning_path_progress:
            print(f"[DEBUG] Triggering Learning Path Progress Update for {self.module.learning_path.path_name}")
            learning_path_progress.calculate_progress()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calculate_progress()

    def __str__(self):
        return f"{self.user.username} - {self.module.module_name} - {'Completed' if self.completed else 'In Progress'}"


class LearningPathProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="learning_path_progress")
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="progress")
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.FloatField(default=0.0)

    def calculate_progress(self):
        """Calculate learning path progress based on completed modules."""
        total_modules = self.learning_path.modules.count()
        completed_modules = ModuleProgress.objects.filter(
            user=self.user, module__learning_path=self.learning_path, completed=True
        ).count()

        print(f"[DEBUG] Learning Path: {self.learning_path.path_name} - Completed Modules: {completed_modules}/{total_modules}")

        if total_modules > 0:
            # Round progress percentage to the nearest whole number
            self.progress_percentage = round((completed_modules / total_modules) * 100)
            self.completed = self.progress_percentage == 100
            self.completion_date = timezone.now() if self.completed else None

            # Update learning path progress
            LearningPathProgress.objects.filter(pk=self.pk).update(
                progress_percentage=self.progress_percentage,
                completed=self.completed,
                completion_date=self.completion_date
            )
            print(f"[DEBUG] Learning Path Progress Updated: {self.progress_percentage}% - Completed: {self.completed}")

        # Trigger course progress update
        course_progress, created = CourseProgress.objects.get_or_create(
            user=self.user, course=self.learning_path.course
        )
        if created:
            print(f"[DEBUG] Created new Course Progress for {self.learning_path.course.course_name}")
        course_progress.calculate_progress()

    def save(self, *args, **kwargs):
        """Override save to calculate progress after updates."""
        super().save(*args, **kwargs)
        self.calculate_progress()

    def __str__(self):
        return f"{self.user.username} - {self.learning_path.path_name} - {self.progress_percentage}% Complete"



class CourseProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_progress")
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.FloatField(default=0.0)

    def calculate_progress(self):
        """Calculate course progress based on completed learning paths."""
        total_learning_paths = self.course.learning_paths.count()
        completed_learning_paths = 0
        total_progress = 0

        for learning_path in self.course.learning_paths.all():
            # Get the progress for each learning path
            learning_path_progress = LearningPathProgress.objects.filter(
                learning_path=learning_path, user=self.user
            ).first()

            if learning_path_progress:
                total_progress += learning_path_progress.progress_percentage
                if learning_path_progress.completed:
                    completed_learning_paths += 1
            else:
                # If no progress is found for this learning path, handle appropriately (e.g., default to 0%)
                total_progress += 0

        # Calculate overall course progress
        if total_learning_paths > 0:
            self.progress_percentage = round(total_progress / total_learning_paths)
            self.completed = self.progress_percentage == 100
            self.completion_date = timezone.now() if self.completed else None

        # Save the course progress after calculating
        CourseProgress.objects.filter(pk=self.pk).update(
            progress_percentage=self.progress_percentage,
            completed=self.completed,
            completion_date=self.completion_date
        )

        print(f"[DEBUG] Course Progress Updated: {self.progress_percentage}% - Completed: {self.completed}")
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calculate_progress()

    def __str__(self):
        return f"{self.user.username} - {self.course.course_name} - {self.progress_percentage}% Complete"




class QuizProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_progress")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)

    def calculate_progress(self):
        self.completed = self.score >= 70.0  # Passing score of 70%
        if self.completed:
            self.completion_date = timezone.now()
        else:
            self.completion_date = None

        # Use `update` instead of `save` to avoid recursion
        QuizProgress.objects.filter(pk=self.pk).update(
            completed=self.completed,
            completion_date=self.completion_date
        )

        # Update module progress when quiz is passed
        module_progress = ModuleProgress.objects.filter(user=self.user, module=self.quiz.module).first()
        if module_progress:
            module_progress.quiz_completed = self.completed
            module_progress.calculate_progress()


    def __str__(self):
        return f"{self.user.username} - {self.quiz.quiz_name} - {'Completed' if self.completed else 'In Progress'}"
    
