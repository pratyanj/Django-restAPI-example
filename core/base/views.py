from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import PersonSerializer
from .models import Person
import requests
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
# @api_view(['GET'])
def index(request:requests.Request):
    courses = {
        'courses': [
            {
                'id': 1,
                'title': 'Python',
                'description': 'Python is a programming language',
                'price': 100
            },
            {
                'id': 2,
                'title': 'JavaScript',
                'description': 'JavaScript is a programming language',
                'price': 200
            },
            {
                'id': 3,
                'title': 'Django',
                'description': 'Django is a web framework',
                'price': 300
            }
        ]
    }
    if request.method == "GET":
        print("GET method called")
    elif request.method == "POST":
        print("POST method called")
    elif request.method == "PUT":
        print("PUT method called")
    elif request.method == "DELETE":
        print("DELETE method called")
    return Response(courses)

@api_view(['GET', 'POST', 'PUT', 'PATCH','DELETE'])
def person_data(request:requests.Request):
    if request.method == "GET":
        print("GET method called")
        person = Person.objects.all()
        serializer_person = PersonSerializer(person, many=True)
        return Response(serializer_person.data)
    
    elif request.method == "POST":  
        print("POST method called")
        serializer = PersonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)
    
    elif request.method == "PUT":
        print("PUT method called")
        print(request.data)
        person = Person.objects.get(id = request.data['id'])
        serializer = PersonSerializer(person, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)   
     
    elif request.method == "PATCH":
        print("PATCH method called")
        person = Person.objects.get(id = request.data['id'])
        serializer = PersonSerializer(person, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)
    
    elif request.method == "DELETE":
        print("DELETE method called")
        person = Person.objects.get(id = request.data['id'])
        person.delete()
        return Response("Person deleted successfully")
        
    
json = {
"name":"pratyanj",
"age":2,
"address":"pratyanj@gmail.com"
}