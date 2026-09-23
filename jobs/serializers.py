from rest_framework import serializers
from .models import Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job  # which model this serializer wraps
        fields = ['id', 'input_file', 'status', 'result', 'error_message', 'created_at', 'updated_at']  # fields exposed in the API
        read_only_fields = ['id', 'status', 'result', 'error_message', 'created_at', 'updated_at']  # fields the client can't set manually