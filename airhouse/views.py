from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View, CreateView, UpdateView, DeleteView, ListView, DetailView
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from .forms import UserRegisterForm, InventoryItemForm, OrderForm, OrderItemFormSet, CategoryForm
from django_filters.views import FilterView
from .filters import OrderFilter, InventoryFilter
from .models import InventoryItem, Category, Order
from airhouse_project.settings import LOW_QUANTITY
from django.contrib import messages

class EntryPage(TemplateView):
    template_name = 'airhouse/entry_page.html'

    def dispatch(self, request, *args, **kwargs):
        # Log out the user if they are logged in
        if request.user.is_authenticated:
            logout(request)
        return super().dispatch(request, *args, **kwargs)

class Index(TemplateView):
    template_name = 'airhouse/index.html'

class LoginView(LoginView):
    template_name = 'airhouse/login.html'

class SignUpView(View):
    def get(self, request):
        form = UserRegisterForm()
        return render(request, 'airhouse/signup.html', {'form': form})
    
    def post(self, request):
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Save the user instance
            
            
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password1')
            
            # Authenticate the user
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('index')
            else:
                # If authentication fails, handle it (e.g., return an error message)
                form.add_error(None, "Authentication failed.")
        # If form is not valid or authentication fails, re-render the form with errors
        return render(request, 'airhouse/signup.html', {'form': form})
    

class Dashboard(LoginRequiredMixin, View):
    def get(self, request):
        # Get all items for the current user
        items = InventoryItem.objects.filter(user=request.user.id).order_by('id')
        
        # Apply the filter
        inventory_filter = InventoryFilter(request.GET, queryset=items)

        # Filtered items
        filtered_items = inventory_filter.qs

        # Find low inventory items within the filtered queryset
        low_inventory = filtered_items.filter(quantity__lte=LOW_QUANTITY)
        if low_inventory.count() > 0:
            message_text = f'{low_inventory.count()} item{"s" if low_inventory.count() > 1 else ""} {"have" if low_inventory.count() > 1 else "has"} low inventory.'
            messages.error(request, message_text)
        
        low_inventory_ids = low_inventory.values_list('id', flat=True)

        # Pass both the filter and filtered items to the template
        return render(request, 'airhouse/dashboard.html', {
            'filter': inventory_filter,  # Pass the filter to the template to render the form
            'items': filtered_items,  # Now passing filtered items
            'low_inventory_ids': low_inventory_ids,
        })
    
    
# CATEGORIES
class CreateCategoryView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'airhouse/category_form.html' 
    success_url = reverse_lazy('dashboard')    

# INVENTORY ITEMS
class AddItem(LoginRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'airhouse/item_form.html'
    success_url = reverse_lazy('dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class EditItem(LoginRequiredMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'airhouse/item_form.html'
    success_url = reverse_lazy('dashboard')

class DeleteItem(LoginRequiredMixin, DeleteView):
    model = InventoryItem
    template_name = 'airhouse/delete_item.html'
    success_url = reverse_lazy('dashboard')
    context_object_name = 'item'


# ORDERS
class Orders(LoginRequiredMixin, FilterView):
    model = Order
    template_name = 'airhouse/orders.html'
    context_object_name = 'orders'
    filterset_class = OrderFilter

    def get_queryset(self):
        # Get the current logged-in user
        user = self.request.user
        
        # Filter orders based on the company name associated with the user's inventory items
        if user.is_authenticated:
            return Order.objects.filter(skus_ordered__user=user)
        else:
            return Order.objects.none()  # Return an empty queryset if the user is not logged in

class OrderDetail(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'airhouse/order_detail.html'
    context_object_name = 'order'


class AddOrder(LoginRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'airhouse/order_form.html'
    success_url = reverse_lazy('orders')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = OrderItemFormSet(self.request.POST, instance=self.object)
        else:
            formset = OrderItemFormSet(instance=self.object)
            context['formset'] = formset
        return context


    def form_valid(self, form):
        context = self.get_context_data()
        orderitems = context['formset']
        if orderitems.is_valid():
            self.object = form.save()
            orderitems.instance = self.object
            orderitems.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


class EditOrder(LoginRequiredMixin, UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'airhouse/order_form.html'
    
    def get_context_data(self, **kwargs):
        context = super(EditOrder, self).get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = OrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = OrderItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            response = super(EditOrder, self).form_valid(form)
            formset.instance = self.object
            formset.save()
            return response
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy('order-detail', kwargs={'pk': self.object.pk})

class DeleteOrder(LoginRequiredMixin, DeleteView):
    model = Order
    template_name = 'airhouse/delete_order.html'
    success_url = reverse_lazy('orders')
    context_object_name = 'order'


class Restock(LoginRequiredMixin, View):
    def get(self, request):
        return self.render_restock_page(request)

    def post(self, request):
        # Extract necessary data from the POST request
        item_id = request.POST.get('item_id')
        adjust_amount = int(request.POST.get('adjust_amount'))
        action = request.POST.get('action')

        # Fetch the specific inventory item
        item = InventoryItem.objects.get(id=item_id, user=request.user)

        # Adjust the item quantity based on the action
        if action == 'add':
            item.quantity += adjust_amount
        elif action == 'subtract':
            item.quantity = max(item.quantity - adjust_amount, 0)  # Prevent negative quantities

        # Save the updated item
        item.save()

        # After processing, render the same page again with updated context
        return self.render_restock_page(request)

    def render_restock_page(self, request):
        # Get all items and those with low inventory
        items = InventoryItem.objects.filter(user=request.user.id).order_by('id')
        low_inventory = items.filter(quantity__lte=LOW_QUANTITY)
        low_inventory_ids = low_inventory.values_list('id', flat=True)

        # Render the restock page with the items and low inventory info
        return render(request, 'airhouse/restock.html', {
            'items': items,
            'low_inventory_ids': low_inventory_ids
        })

# BILLING
class Billing(LoginRequiredMixin, TemplateView):
    template_name = 'airhouse/billing.html'

class Returns(LoginRequiredMixin, TemplateView):
    template_name = 'airhouse/returns.html'

class Projects(LoginRequiredMixin, TemplateView):
    template_name = 'airhouse/projects.html'

class Refer(LoginRequiredMixin, TemplateView):
    template_name = 'airhouse/refer.html'

class Help(LoginRequiredMixin, TemplateView):
    template_name = 'airhouse/help.html'