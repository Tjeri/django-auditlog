import json

from auditlog.diff import model_instance_diff
from auditlog.models import LogEntry


def log_create(sender, instance, created, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is first saved to the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if created:
        changes = model_instance_diff(None, instance)

        log_entry = LogEntry.objects.log_create(
            instance,
            action=LogEntry.Action.CREATE,
            changes=json.dumps(changes),
        )


def log_update(sender, instance, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is changed and saved to the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if instance.pk is not None:
        try:
            old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            pass
        else:
            new = instance

            changes = model_instance_diff(old, new)

            # Log an entry only if there are changes
            if changes:
                log_entry = LogEntry.objects.log_create(
                    instance,
                    action=LogEntry.Action.UPDATE,
                    changes=json.dumps(changes),
                )


def log_delete(sender, instance, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is deleted from the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if instance.pk is not None:
        changes = model_instance_diff(instance, None)

        log_entry = LogEntry.objects.log_create(
            instance,
            action=LogEntry.Action.DELETE,
            changes=json.dumps(changes),
        )


def log_m2m_change(sender, instance, action, pk_set, **kwargs):
    """
    Signal receiver that creates a log entry when an m2m field on a model instance is changed and saved to the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if instance.pk is None or action == 'post_clear':
        return
    if action == 'pre_clear':
        _log_m2m_clear(sender, instance)
        return
    if not action.startswith('post_') or len(pk_set) == 0:
        return
    field, _ = _get_field(sender, instance)
    if field.name is None:
        return
    LogEntry.objects.log_create(
        instance,
        action=LogEntry.Action.M2M_CHANGE,
        changes=json.dumps({field.name: [action[5:], list(pk_set)]}),
    )


def _log_m2m_clear(sender, instance):
    field, _field = _get_field(sender, instance)
    cleared = [item.pk for item in _field.all()]
    if field.name is None or len(cleared) == 0:
        return
    LogEntry.objects.log_create(
        instance,
        action=LogEntry.Action.M2M_CHANGE,
        changes=json.dumps({field.name: ['clear', cleared]}),
    )


def _get_field(sender, instance):
    from django.db.models import ManyToManyField
    for field in instance._meta.get_fields():
        if isinstance(field, ManyToManyField):
            _field = getattr(instance, field.name)
            if hasattr(_field, 'through') and _field.through is sender:
                return field, _field
