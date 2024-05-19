from rest_framework import serializers


class WayForPayCallbackSerializer(serializers.Serializer):
    orderReference = serializers.CharField()
    reasonCode = serializers.CharField()
    time = serializers.CharField()
    signature = serializers.CharField()
