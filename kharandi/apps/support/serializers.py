from rest_framework import serializers
from .models import Ticket, TicketMessage

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Ticket
        fields = ["id","ticket_number","subject","description","category","order_number","priority","status","created_at"]
        read_only_fields = ["ticket_number","status","created_at"]

class TicketMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    class Meta:
        model  = TicketMessage
        fields = ["id","author_name","content","is_internal","attachment","created_at"]
        read_only_fields = ["author_name","created_at"]
