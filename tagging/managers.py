from django.core.cache import get_cache
from django.core.cache.backends.base import InvalidCacheBackendError
from tagging.models import *


class TagManager(models.Manager):
    """Provides an interface to the tagging system"""

    def __init__(self, cache=None):
        super(TagManager, self).__init__()
        if cache:
            try:
                self.CACHE = get_cache(cache)
            except InvalidCacheBackendError:
                self.CACHE = None
        else:
            self.CACHE = None

    @staticmethod
    def add(obj, **kwargs):
        c_type = ContentType.objects.get_for_model(obj)
        for tag in Tag.objects.filter(**kwargs):
            TaggedItem.objects.get_or_create(tag=tag, content_type=c_type, object_id=obj.id)

    @staticmethod
    def add_by_kv(obj, **kwargs):
        c_type = ContentType.objects.get_for_model(obj)
        for key_value in KeyValue.objects.filter(**kwargs):
            TaggedItem.objects.get_or_create(tag=key_value.tag, content_type=c_type, object_id=obj.id)

    @staticmethod
    def remove(obj, **kwargs):
        c_type = ContentType.objects.get_for_model(obj)
        for tag in Tag.objects.filter(**kwargs):
            try:
                item = TaggedItem.objects.get(tag=tag, content_type=c_type, object_id=obj.id)
                item.delete()
            except TaggedItem.DoesNotExist:
                pass

    @staticmethod
    def remove_by_kv(obj, **kwargs):
        c_type = ContentType.objects.get_for_model(obj)
        for key_value in KeyValue.objects.filter(**kwargs):
            try:
                item = TaggedItem.objects.get(tag=key_value.tag, content_type=c_type, object_id=obj.id)
                item.delete()
            except TaggedItem.DoesNotExist:
                pass

    @staticmethod
    def filter(obj, **kwargs):
        c_type = ContentType.objects.get_for_model(obj)
        tag_ids = TaggedItem.objects.filter(object_id=obj.id, content_type=c_type).values('tag')
        return Tag.objects.filter(pk__in=tag_ids, **kwargs)

    @staticmethod
    def get_list(obj):
        """Returns a list of Tag model instances bound to given object"""
        c_type = ContentType.objects.get_for_model(obj)
        ret = []

        for item in TaggedItem.objects.filter(content_type=c_type, object_id=obj.id).values('tag'):
            tag = Tag.objects.prefetch_related('kv_pairs').get(pk=item['tag'])
            ret.append(tag)

        return ret

    def get_digest_list(self, obj):
        """Returns a list of objects which contains digested data of Tags bound to given object"""
        c_type = ContentType.objects.get_for_model(obj)
        ret = []

        if self.CACHE:
            tags = self.CACHE.get('tags')
            item_tags = self.CACHE.get('item_tags')

            if tags is None:
                print "missed cache for tags"
                tags = self.populate_tags_dictionary()
                self.CACHE.set('tags', tags)
            else:
                print "hit cache for tags"

            if item_tags is None:
                print "missed cache for item_tags"
                item_tags = self.populate_item_tag_lists_dictionary()
                self.CACHE.set('item_tags', item_tags)
            else:
                print "hit cache for item_tags"

            if c_type in item_tags and obj.id in item_tags[c_type]:
                for tag_id in item_tags[c_type][obj.id]:
                    ret.append(tags[tag_id])

        else:
            tag_ids = TaggedItem.objects.filter(content_type=c_type, object_id=obj.id).values('tag')
            for tag in Tag.objects.filter(pk__in=tag_ids):
                obj = {'id': tag.id, 'key': tag.key}
                for key_value in tag.kv_pairs.all():
                    obj[key_value.key] = key_value.value
                ret.append(obj)

        return ret

    @staticmethod
    def populate_tags_dictionary():
        """ This creates a dictionary for tags whose keys are tag IDs and values are digest tag objects. """
        tags = {}
        for tag in Tag.objects.select_related().prefetch_related('kv_pairs').all():
            obj = {'id': tag.id, 'key': tag.key}
            for key_value in tag.kv_pairs.all():
                obj[key_value.key] = key_value.value
            tags[tag.id] = obj
        return tags

    @staticmethod
    def populate_item_tag_lists_dictionary():
        """ This creates a 2-level dictionary.
        First level keys are content_types and second level keys are object_ids.
        Values are list of tag IDs associated with that content_type and object_id pair.
        """
        item_tags = {}
        for item in TaggedItem.objects.all():
            if item.tag.id:
                if item.content_type in item_tags:
                    if item.object_id in item_tags[item.content_type]:
                        item_tags[item.content_type][item.object_id].append(item.tag.id)
                    else:
                        item_tags[item.content_type][item.object_id] = [item.tag.id]
                else:
                    item_tags[item.content_type] = {}
                    item_tags[item.content_type][item.object_id] = [item.tag.id]
        return item_tags