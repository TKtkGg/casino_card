from django.shortcuts import render

# Create your views here.
def top(request):
    return render(request, 'casino/top.html')

def bacarrat(request):
    return render(request, 'casino/bacarrat.html')