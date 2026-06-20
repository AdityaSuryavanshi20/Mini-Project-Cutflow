from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('projects', '0001_initial'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel('Quotation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quotations', to='projects.project')),
            ('quote_no', models.CharField(max_length=30, unique=True)),
            ('revision', models.PositiveSmallIntegerField(default=1)),
            ('status', models.CharField(choices=[('draft','Draft'),('sent','Sent to Customer'),('accepted','Accepted'),('rejected','Rejected'),('revised','Revised'),('expired','Expired')], default='draft', max_length=20)),
            ('quote_date', models.DateField(auto_now_add=True)),
            ('valid_until', models.DateField(blank=True, null=True)),
            ('salesman', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quotations', to='auth.user')),
            ('installation_type', models.CharField(choices=[('percent','Percentage'),('sqft','Per Sqft'),('fixed','Fixed')], default='percent', max_length=10)),
            ('installation_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ('freight', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ('lifting_charges', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ('discount_type', models.CharField(choices=[('percent','Percentage'),('fixed','Fixed')], default='percent', max_length=10)),
            ('discount_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ('apply_sgst', models.BooleanField(default=True)),
            ('apply_cgst', models.BooleanField(default=True)),
            ('apply_igst', models.BooleanField(default=False)),
            ('sgst_rate', models.DecimalField(decimal_places=2, default=9, max_digits=5)),
            ('cgst_rate', models.DecimalField(decimal_places=2, default=9, max_digits=5)),
            ('igst_rate', models.DecimalField(decimal_places=2, default=18, max_digits=5)),
            ('payment_terms', models.TextField(blank=True)),
            ('notes', models.TextField(blank=True)),
            ('internal_notes', models.TextField(blank=True)),
            ('sent_at', models.DateTimeField(blank=True, null=True)),
            ('sent_to_email', models.EmailField(blank=True)),
            ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quotations_created', to='auth.user')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel('QuotationItem', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('quotation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='quotations.quotation')),
            ('measurement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='projects.measurementitem')),
            ('line_no', models.CharField(max_length=10)),
            ('reference', models.CharField(blank=True, max_length=20)),
            ('location', models.CharField(blank=True, max_length=100)),
            ('system', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.system')),
            ('glass', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='catalog.glass')),
            ('color', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='catalog.color')),
            ('description', models.CharField(blank=True, max_length=255)),
            ('width', models.IntegerField()),
            ('height', models.IntegerField()),
            ('qty', models.PositiveIntegerField(default=1)),
            ('n_panels', models.PositiveSmallIntegerField(default=1)),
            ('unit_rate', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('weight_kg', models.DecimalField(decimal_places=3, default=0, max_digits=10)),
            ('notes', models.TextField(blank=True)),
            ('sort_order', models.PositiveSmallIntegerField(default=0)),
        ], options={'ordering': ['sort_order', 'line_no']}),
    ]
