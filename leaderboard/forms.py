from django import forms

from .models import ScoreCategory, ScoreEntry
from .number_fields import UnlimitedIntegerFormField


class ScoreEntryAdminForm(forms.ModelForm):
    points = UnlimitedIntegerFormField(
        label="Points",
        help_text="Enter any whole number. Use a minus sign for a deduction.",
        widget=forms.TextInput(attrs={"inputmode": "text", "autocomplete": "off"}),
    )

    class Meta:
        model = ScoreEntry
        fields = ("member", "category", "points", "reason", "date_awarded")
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
            "date_awarded": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("Explain why these points are being awarded or deducted.")
        return reason

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "category" in self.fields:
            self.fields["category"].queryset = ScoreCategory.objects.filter(is_active=True)
