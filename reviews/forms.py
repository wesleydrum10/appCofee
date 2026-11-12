from django import forms

from .models import StoreFeedback


class StoreFeedbackForm(forms.ModelForm):
    class Meta:
        model = StoreFeedback
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.RadioSelect(choices=[(value, f"{value} estrelas") for value in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 4, "maxlength": 1000}),
        }
