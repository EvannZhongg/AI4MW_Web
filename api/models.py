# api/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Device(models.Model):
    # 基础信息字段
    name = models.CharField(max_length=100, verbose_name="器件名称")
    device_type = models.CharField(max_length=50, verbose_name="器件类型")
    substrate = models.CharField(max_length=50, verbose_name="衬底材料")
    device_number = models.CharField(max_length=100, unique=True, verbose_name="器件编号")
    # test_type 字段已被移除
    tech_description = models.TextField(blank=True, null=True, verbose_name="技术说明")
    photo_data = models.TextField(blank=True, null=True, verbose_name="微观照片 (Base64)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    # 此字段将存储一个列表，每个列表项是一个包含 name, experiment_type, grid_data, csv_files 的对象
    device_specific_data = models.JSONField(null=True, blank=True, default=list, verbose_name="器件自定义数据")

    def __str__(self):
        return self.device_number

    class Meta:
        verbose_name = "器件"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        
class ProbabilityDataSet(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="数据集名称")
    # 存储完整的曲线数据，例如 {'x': [...], 'y': [...]}
    data = models.JSONField(verbose_name="概率数据")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "概率数据集"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class Profile(models.Model):
    """
    重构后的Profile模型。
    - 使用JSONField存储一个包含多套用户自定义配置的列表。
    - 使用CharField存储当前激活的配置ID ('default' 或自定义配置的ID)。
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # 存储一个配置对象的列表，例如:
    # [
    #   { "id": 1678886400000, "name": "我的GPT-4", "llm_api_url": "...", "llm_api_key": "...", "llm_model_name": "..." },
    #   ...
    # ]
    user_configs = models.JSONField(
        default=list,
        blank=True,
        verbose_name="用户自定义API配置列表"
    )

    # 存储当前激活的配置ID。可以是 'default' 字符串，或者是 user_configs 中某个配置的 id
    active_config_id = models.CharField(
        max_length=50,
        default='default',
        blank=True,
        verbose_name="当前激活的配置ID"
    )

    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()