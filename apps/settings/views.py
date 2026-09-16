from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from .models import PaymentSetting
from .forms import PaymentSettingForm
from apps.superadmin.models import Gym
from apps.superadmin.forms import GymForm
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from apps.login.decorators import custom_permission_required

class generalsetting(TemplateView):
    template_name = "settings/general_settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gym = getattr(self.request, 'gym', None)
        context['gym'] = gym
        if gym:
            context['form'] = GymForm(instance=gym)
        return context

    def post(self, request, *args, **kwargs):
        gym = getattr(request, 'gym', None)
        if not gym:
            # Handle case where gym is not found
            messages.error(request, 'Gym not found.')
            return redirect('settings:general_settings')

        form = GymForm(request.POST, request.FILES, instance=gym)
        if form.is_valid():
            form.save()
            messages.success(request, 'General settings saved successfully.')
            return redirect('settings:gym_profile')

        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)

@method_decorator(custom_permission_required('change_paymentsetting'), name='dispatch')
class PaymentSettingView(LoginRequiredMixin, View):
    template_name = 'settings/payment_setting.html'

    def get(self, request, *args, **kwargs):
        gym = request.gym
        payment_settings, created = PaymentSetting.objects.get_or_create(gym=gym)
        form = PaymentSettingForm(instance=payment_settings)
        return render(request, self.template_name, {'form': form, 'payment_settings': payment_settings})

    def post(self, request, *args, **kwargs):
        gym = request.gym
        payment_settings, created = PaymentSetting.objects.get_or_create(gym=gym)
        form = PaymentSettingForm(request.POST, request.FILES, instance=payment_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment settings saved successfully.')
            return redirect('settings:payment_setting')
        return render(request, self.template_name, {'form': form, 'payment_settings': payment_settings})

@method_decorator(custom_permission_required('change_paymentsetting'), name='dispatch')
class GymProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'settings/gym_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['gym'] = getattr(self.request, 'gym', None)
        return context