from django.db import models

class Student(models.Model):
    student_id = models.IntegerField(default=1)
    name = models.CharField(max_length=100, default='')
    branch = models.CharField(max_length=50, default='')
    artificial_intelligence = models.IntegerField(default=0)
    machine_learning = models.IntegerField(default=0)
    python = models.IntegerField(default=0)
    deep_learning = models.IntegerField(default=0)
    maths = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)
    cgpa = models.FloatField(default=0.0)
    status = models.CharField(max_length=10, default='Pass')
    failed_subjects = models.CharField(max_length=200, default='None')

    def __str__(self):
        return f"{self.name} ({self.branch}) - CGPA: {self.cgpa}"

class Teacher(models.Model):
    teacher_id = models.IntegerField(default=101)
    name = models.CharField(max_length=100, default='')
    subject = models.CharField(max_length=100, default='')
    department = models.CharField(max_length=50, default='')
    hod_name = models.CharField(max_length=100, default='')
    experience_years = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.subject} (HOD: {self.hod_name})"
