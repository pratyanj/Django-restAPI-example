from django.contrib import admin
from .models import Person, gender
# Register your models here.
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')

admin.site.register(Person, PersonAdmin)
admin.site.register(gender)
