from django.contrib import admin
from .models import Person, Gender
# Register your models here.
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'address',"sex",'age')

admin.site.register(Person, PersonAdmin)
admin.site.register(Gender)
