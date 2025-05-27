from rest_framework import serializers
from .models import Person , Gender

class LoginSerializer(serializers.Serializer):
    '''
    serializers.Serializer is a base class provided by Django REST Framework for serializing and deserializing data. 
    It allows you to convert complex data types (like Django models, querysets) into Python native datatypes that can be easily rendered into JSON, XML, or other content types.
    It also provides validation and can convert incoming data back into complex types. Unlike ModelSerializer, it doesn't automatically generate fields based on a model - you need to explicitly declare all fields.    '''
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(max_length=20)

class GenderSerializer(serializers.ModelSerializer):
    '''
    serializers.ModelSerializer is a class provided by Django REST Framework that automatically creates a Serializer class with fields that correspond to the Model fields. 
    It provides default implementations for creating, updating, and deleting model instances, making it easier to convert complex data types like querysets and model instances into Python datatypes that can then be easily rendered into JSON, XML or other content types.
    It also handles validation and can create/update model instances from validated data.  '''
    class Meta:
        model = Gender
        fields = ["sex",'id'] # to get only the fields that are specified
        
class PersonSerializer(serializers.ModelSerializer):
    sex = GenderSerializer()
    country = serializers.SerializerMethodField()
    class Meta:
        model = Person
        fields = '__all__'  # to get all the fields
        # depth = 1           # to get the related data of the foreign key
    
    def get_country(self,obj):
        gender = Gender.objects.get(id=obj.sex.id)
        return { 'Country':"India",'Gender':str(gender)} 
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
