from django.shortcuts import render, redirect , HttpResponse
from django.views import View
from finance.forms import RegisterForm,TransactionForm, GoalForm, ProfileForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Transaction, Goal
from django.db.models import Sum
from django.views.generic.edit import UpdateView
from .models import Profile
from django.urls import reverse_lazy
from .admin import TransactionResource
from django.db.models.functions import TruncMonth
import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserUpdateForm, ProfileUpdateForm

# Create your views here.

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, "finance/home.html")


class RegisterView(View):
    def get(self, request, *args, **kwargs):
        user_form = RegisterForm()
        return render(request, 'finance/register.html', {'form': user_form})

    def post(self, request, *args, **kwargs):
        user_form = RegisterForm(request.POST)
        profile_form = ProfileForm(request.POST, request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            login(request, user)
            return redirect('dashboard')
        return render(request, 'finance/register.html', {'form': user_form, 'profile_form': profile_form})       
class DashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):

        transactions = Transaction.objects.filter(user=request.user)
        goals = Goal.objects.filter(user=request.user)

        # Calculate total income & expense
        total_income = Transaction.objects.filter(
            user=request.user,
            transaction_type='Income'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        total_expense = Transaction.objects.filter(
            user=request.user,
            transaction_type='Expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        net_savings = total_income - total_expense

        # Goal Progress Logic (your existing logic)
        remaining_savings = net_savings
        goal_progress = []

        for goal in goals:
            if remaining_savings >= goal.target_amount:
                goal_progress.append({'goal': goal, 'progress': 100})
                remaining_savings -= goal.target_amount
            elif remaining_savings > 0:
                progress = (remaining_savings / goal.target_amount) * 100
                goal_progress.append({'goal': goal, 'progress': progress})
                remaining_savings = 0
            else:
                goal_progress.append({'goal': goal, 'progress': 0})

        # ==========================
        # 📊 Monthly Chart Data
        # ==========================

        monthly_data = (
            Transaction.objects
            .filter(user=request.user)
            .annotate(month=TruncMonth('date'))
            .values('month', 'transaction_type')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )

        months = []
        income_data = []
        expense_data = []

        for entry in monthly_data:
            month_label = entry['month'].strftime('%b %Y')
            if month_label not in months:
                months.append(month_label)

        for month in months:
            income = sum(
                e['total']
                for e in monthly_data
                if e['month'].strftime('%b %Y') == month and e['transaction_type'] == 'Income'
            )

            expense = sum(
                e['total']
                for e in monthly_data
                if e['month'].strftime('%b %Y') == month and e['transaction_type'] == 'Expense'
            )

            income_data.append(float(income) if income else 0)
            expense_data.append(float(expense) if expense else 0)

        context = {
            'transactions': transactions,
            'total_income': total_income,
            'total_expense': total_expense,
            'net_savings': net_savings,
            'goal_progress': goal_progress,

            # Chart Data
            'months': json.dumps(months),
            'income_data': json.dumps(income_data),
            'expense_data': json.dumps(expense_data),
        }

        return render(request, 'finance/dashboard.html', context)
    
class TransactionCreateView(LoginRequiredMixin,View):
    def get(self, request, *args, **kwargs):
        form = TransactionForm()
        return render(request, 'finance/transaction_form.html', {'form':form})
    
    def post(self, request, *args, **kwargs):
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            return redirect('dashboard')
        return render(request, 'finance/transaction_form.html',{'form':form})

class TransactionListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        transactions = Transaction.objects.filter(user=request.user)
        return render(request, 'finance/transaction_list.html', {'transactions':transactions})
   
class GoalCreateView(LoginRequiredMixin,View):
    def get(self, request, *args, **kwargs):
        form = GoalForm()
        return render(request, 'finance/goal_form.html', {'form':form})
    
    def post(self, request, *args, **kwargs):
        form =GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            return redirect('dashboard')
        return render(request, 'finance/goal_form.html',{'form':form})
    
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = 'finance/profile.html'

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_success_url(self):
        return reverse_lazy('dashboard')
@login_required    
def export_transactions(request):
    user_transactions = Transaction.objects.filter(user=request.user)
    transactions_resource = TransactionResource()
    dataset = transactions_resource.export(queryset=user_transactions)
    excel_data = dataset.export('xlsx')
    #create an HttpResponse with the correct MIME type for excel file
    response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    #set the header for download the file
    response['Content-Disposition']='attachment;filename=transactions_report.xlsx'
    return response

@login_required
def account_settings(request):
    if request.method == "POST":
        print(request.POST)
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user.profile
        )
        user_valid = user_form.is_valid()
        profile_valid = profile_form.is_valid()

        if user_valid:
            user_form.save()

        if profile_valid:
            profile_form.save()

        if user_valid and profile_valid:
            messages.success(request, "Account updated successfully!")
            return redirect("account_settings")

    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    return render(request, "finance/account_settings.html", {
        "user_form": user_form,
        "profile_form": profile_form
    })