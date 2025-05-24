from rest_framework import serializers
from .models import Person

class PersonSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Person
        fields = '__all__' 
    
    def validate(self, data):
        # if data['name'] == "":
        #     raise serializers.ValidationError("Name is required")

        # if data['age'] < 18 :
        #     raise serializers.ValidationError("Age must be greater than 18")
        # elif data['age'] > 100 :
        #     raise serializers.ValidationError("Age must be less than 100")
        
        if data['address'] == "":
            raise serializers.ValidationError("Email is required")
        return data
    
    def validate_age(self, value:int):
        if value < 18 :
            raise serializers.ValidationError("Age must be greater than 18")
        elif value > 100 :
            raise serializers.ValidationError("Age must be less than 100")
        return value
    
    def validate_name(self, value:str):
        if value == "":
            raise serializers.ValidationError("Name is required")
        elif value.isdigit():
            raise serializers.ValidationError("Name must be a string")
        special_characters = "!@#$%^&*()_+-=[]{}|;':\",.<>?/\\"
        for char in value:
            if char in special_characters:
                raise serializers.ValidationError("Name must not contain special characters")
        return value
        
    def create(self, validated_data):
        return Person.objects.create(**validated_data)
