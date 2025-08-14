from django.db import models

# 1️⃣ Staff / Service Providers
class Staff(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# 2️⃣ Staff Availability
class StaffAvailability(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="availability")
    day_of_week = models.IntegerField(choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('staff', 'day_of_week')

    def __str__(self):
        return f"{self.staff} - {self.get_day_of_week_display()} ({self.start_time} - {self.end_time})"

# 3️⃣ Base Service Model (abstract)
class BaseService(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    staff = models.ManyToManyField(Staff, related_name="%(class)s_services")  # Multiple staff per service

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

# 4️⃣ Individual Service Tables
class Haircut(BaseService):
    pass

class BeardCut(BaseService):
    pass

class Facial(BaseService):
    pass

class Spa(BaseService):
    pass

# 5️⃣ Customer Table
class Customer(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# 6️⃣ Booking Table
class Booking(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('haircut', 'Haircut'),
        ('beard', 'BeardCut'),
        ('facial', 'Facial'),
        ('spa', 'SPA'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="bookings")
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPE_CHOICES)
    service_id = models.PositiveIntegerField()  # ID from corresponding service table
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    booking_date = models.DateField()
    booking_time = models.TimeField()
    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer} - {self.service_type} on {self.booking_date} at {self.booking_time}"
