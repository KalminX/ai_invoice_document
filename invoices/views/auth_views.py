from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Clean enterprise login view with quick demo user switcher."""
    if request.user.is_authenticated:
        return redirect('invoices:dashboard')

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next') or 'invoices:dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, 'invoices/auth/login.html')


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('invoices:login')
