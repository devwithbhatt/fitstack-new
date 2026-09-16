from django import forms
from .models import PaymentSetting

class PaymentSettingForm(forms.ModelForm):
    class Meta:
        model = PaymentSetting
        fields = ['bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'qr_code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False