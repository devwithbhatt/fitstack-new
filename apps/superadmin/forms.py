from django import forms
from django.contrib.auth.models import User
from .models import Gym, SubscriptionPlan

class GymForm(forms.ModelForm):

    class Meta:
        model = Gym
        fields = ['name', 'gym_id_prefix', 'slogan', 'logo', 'pincode', 'address', 'area', 'city', 'state', 'phone', 'landline', 'email', 'website', 'note', 'gst_enabled', 'gst_rate', 'gst_number', 'attendance_code_required']
        widgets = {
            'logo': forms.FileInput,
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def __init__(self, *args, **kwargs):
        super(GymForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = 'Enter the name of the gym'
        self.fields['gym_id_prefix'].widget.attrs['placeholder'] = 'Enter a prefix for gym IDs'
        self.fields['slogan'].widget.attrs['placeholder'] = 'Enter a slogan for the gym'
        self.fields['address'].widget.attrs['placeholder'] = 'Enter the address of the gym'
        self.fields['phone'].widget.attrs['placeholder'] = 'Enter the phone number'
        self.fields['landline'].widget.attrs['placeholder'] = 'Enter the landline number'
        self.fields['email'].widget.attrs['placeholder'] = 'Enter the email address'
        self.fields['website'].widget.attrs['placeholder'] = 'Enter the website URL'
        self.fields['note'].widget.attrs['placeholder'] = 'Enter any additional notes'
        self.fields['gst_rate'].widget.attrs['placeholder'] = 'Enter GST Rate'
        self.fields['gst_number'].widget.attrs['placeholder'] = 'Enter GST Number'
        self.fields['logo'].widget.attrs.update({'class': 'custom-file-input'})
        for field_name, field in self.fields.items():
            if field_name in ['gst_enabled', 'attendance_code_required']:
                field.widget.attrs.update({'class': 'form-check-input', 'role': 'switch'})
            elif field_name != 'logo':
                field.widget.attrs.update({'class': 'form-control'})

class GymAdminForm(forms.ModelForm):
    name = forms.CharField(max_length=150, required=True)
    Phone_number = forms.CharField(max_length=15, required=True)
    photo = forms.ImageField(required=False)
    Department = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and ' ' in password:
            raise forms.ValidationError("Password cannot contain spaces.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ['name', 'price', 'duration_months', 'features']

    def __init__(self, *args, **kwargs):
        super(SubscriptionPlanForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = 'Enter the name of the plan'
        self.fields['price'].widget.attrs['placeholder'] = 'Enter the price'
        self.fields['duration_months'].widget.attrs['placeholder'] = 'Enter the duration in months'
        self.fields['features'].widget.attrs['placeholder'] = 'Enter the features of the plan'
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'