from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.response import Response
from base.serializers import PersonSerializer
from base.models import Person

class IndexV2View(APIView):
    def get(self, request):
        return Response({
            'version': '2.0',
            'message': 'Welcome to API v2',
            'endpoints': ['/persons/', '/index/']
        })

class PersonV2ViewSet(viewsets.ModelViewSet):
    serializer_class = PersonSerializer
    queryset = Person.objects.all()
    
    def list(self, request):
        search_query = request.GET.get('search')
        queryset = self.queryset
        
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
            
        serializer = PersonSerializer(queryset, many=True)
        return Response({
            'version': '2.0',
            'count': len(serializer.data),
            'data': serializer.data
        })