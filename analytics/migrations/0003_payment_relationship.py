from django.db import migrations,models
import django.db.models.deletion
import django.utils.timezone
class Migration(migrations.Migration):
 dependencies=[("analytics","0002_intelligence")]
 operations=[migrations.CreateModel(name="PaymentRelationship",fields=[
  ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
  ("payment_amount",models.DecimalField(blank=True,decimal_places=2,max_digits=22,null=True)),
  ("payment_count",models.PositiveBigIntegerField(blank=True,null=True)),
  ("source_file",models.CharField(blank=True,max_length=240)),
  ("imported_at",models.DateTimeField(default=django.utils.timezone.now)),
  ("is_demo",models.BooleanField(default=False)),
  ("beneficiary",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="incoming_payments",to="analytics.company")),
  ("payer",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="outgoing_payments",to="analytics.company"))],
  options={"constraints":[models.UniqueConstraint(fields=("payer","beneficiary","source_file"),name="uniq_payment_pair_source")],"indexes":[models.Index(fields=["payer","beneficiary"],name="analytics_pa_payer_i_6c0a4f_idx")]})]