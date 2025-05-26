from django.db import models
from django.db.models import EmailField

class gender(models.Model):
    sex = models.CharField(max_length=100)
    
    def __str__(self):
        return self.sex
# Create your models here.
class Person(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    address = EmailField()
    sex = models.ForeignKey(gender, on_delete=models.CASCADE,related_name='gender', null=True, blank=True)
    #add null=True, blank=True if there is already data in the database