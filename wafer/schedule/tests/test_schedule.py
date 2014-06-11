from django.test import Client, TestCase
from django.contrib.auth.models import User

import datetime as D
from wafer.talks.models import Talk, ACCEPTED, REJECTED, PENDING
from wafer.pages.models import Page
from wafer.schedule.models import Day, Venue, Slot, ScheduleItem
from wafer.schedule.admin import (find_overlapping_slots, validate_items,
                                  find_duplicate_schedule_items,
                                  find_clashes, find_invalid_venues)


class ScheduleTests(TestCase):

    def _make_pages(self, n):
        # Utility function
        pages = []
        for x in range(n):
            page = Page.objects.create(name="test page %s" % x,
                                       slug="test%s" % x)
            pages.append(page)
        return pages

    def _make_items(self, venues, pages):
        # Utility function
        items = []
        for x, (venue, page) in enumerate(zip(venues, pages)):
            item = ScheduleItem.objects.create(venue=venue,
                                               details="Item %s" % x,
                                               page_id=page.pk)
            items.append(item)
        return items

    def test_days(self):
        """Create some days and check the results."""
        Day.objects.create(date=D.date(2013, 9, 22))
        Day.objects.create(date=D.date(2013, 9, 23))

        assert Day.objects.count() == 2

        output = ["%s" % x for x in Day.objects.all()]

        assert output == ["Sep 22 (Sun)", "Sep 23 (Mon)"]

    def test_venue_list(self):
        """Create venues and check that we get the expected list back"""
        Venue.objects.create(order=2, name='Venue 2')
        Venue.objects.create(order=1, name='Venue 1')

        assert Venue.objects.count() == 2

        c = Client()
        response = c.get('/schedule/')

        assert len(response.context['venue_list']) == 2
        assert response.context["venue_list"][0].name == "Venue 1"
        assert response.context["venue_list"][1].name == "Venue 2"

    def test_simple_table(self):
        """Create a simple, single day table with 3 slots and 2 venues and
           check we get the expected results"""

        # Schedule is
        #         Venue 1     Venue 2
        # 10-11   Item1       Item4
        # 11-12   Item2       Item5
        # 12-13   Item3       Item6
        day1 = Day.objects.create(date=D.date(2013, 9, 22))

        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue1.days.add(day1)
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue2.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        start3 = D.time(12, 0, 0)
        end = D.time(13, 0, 0)

        pages = self._make_pages(6)
        venues = [venue1, venue1, venue1, venue2, venue2, venue2]
        items = self._make_items(venues, pages)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(previous_slot=slot1, end_time=start3,
                                    day=day1)
        slot3 = Slot.objects.create(previous_slot=slot2, end_time=end,
                                    day=day1)

        items[0].slots.add(slot1)
        items[3].slots.add(slot1)
        items[1].slots.add(slot2)
        items[4].slots.add(slot2)
        items[2].slots.add(slot3)
        items[5].slots.add(slot3)

        c = Client()
        response = c.get('/schedule/')

        days = dict(response.context['table_days'])

        assert day1 in days
        assert len(days[day1]) == 3
        assert days[day1][0].slot.get_start_time() == start1
        assert days[day1][0].slot.end_time == start2
        assert days[day1][1].slot.get_start_time() == start2
        assert days[day1][1].slot.end_time == start3
        assert days[day1][2].slot.get_start_time() == start3
        assert days[day1][2].slot.end_time == end

        assert len(days[day1][0].items) == 2
        assert len(days[day1][1].items) == 2
        assert len(days[day1][2].items) == 2

        assert days[day1][0].get_sorted_items()[0]['item'] == items[0]
        assert days[day1][0].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][0].get_sorted_items()[1]['item'] == items[3]
        assert days[day1][0].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[0]['item'] == items[1]
        assert days[day1][1].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][2].get_sorted_items()[1]['item'] == items[5]
        assert days[day1][2].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][2].get_sorted_items()[1]['colspan'] == 1

    def test_ordering(self):
        """Ensure we handle oddly ordered creation of items correctly"""
        # Schedule is
        #         Venue 1     Venue 2
        # 10-11   Item3       Item6
        # 11-12   Item2       Item5
        # 12-13   Item1       Item4
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue1.days.add(day1)
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue2.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        start3 = D.time(12, 0, 0)
        end = D.time(13, 0, 0)

        pages = self._make_pages(6)
        venues = [venue1, venue1, venue1, venue2, venue2, venue2]
        items = self._make_items(venues, pages)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(previous_slot=slot1, end_time=start3,
                                    day=day1)
        slot3 = Slot.objects.create(previous_slot=slot2, end_time=end,
                                    day=day1)

        items[0].slots.add(slot3)
        items[3].slots.add(slot3)
        items[1].slots.add(slot2)
        items[4].slots.add(slot2)
        items[2].slots.add(slot1)
        items[5].slots.add(slot1)

        c = Client()
        response = c.get('/schedule/')

        days = dict(response.context['table_days'])

        assert day1 in days
        assert len(days[day1]) == 3
        assert days[day1][0].slot.get_start_time() == start1
        assert days[day1][0].slot.end_time == start2
        assert days[day1][1].slot.get_start_time() == start2
        assert days[day1][1].slot.end_time == start3
        assert days[day1][2].slot.get_start_time() == start3
        assert days[day1][2].slot.end_time == end

        assert len(days[day1][0].items) == 2
        assert len(days[day1][1].items) == 2
        assert len(days[day1][2].items) == 2

        assert days[day1][0].get_sorted_items()[0]['item'] == items[2]
        assert days[day1][0].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][0].get_sorted_items()[1]['item'] == items[5]
        assert days[day1][0].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[0]['item'] == items[1]
        assert days[day1][1].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][2].get_sorted_items()[1]['item'] == items[3]
        assert days[day1][2].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][2].get_sorted_items()[1]['colspan'] == 1

    def test_multiple_days(self):
        """Create a multiple day table with 3 slots and 2 venues and
           check we get the expected results"""
        # Schedule is
        #         Venue 1     Venue 2
        # Day1
        # 10-11   Item1       Item4
        # 11-12   Item2       Item5
        # Day2
        # 12-13   Item3       Item6
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        day2 = Day.objects.create(date=D.date(2013, 9, 23))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue1.days.add(day1)
        venue1.days.add(day2)
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue2.days.add(day1)
        venue2.days.add(day2)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        end1 = D.time(12, 0, 0)

        start3 = D.time(12, 0, 0)
        end2 = D.time(13, 0, 0)

        pages = self._make_pages(6)
        venues = [venue1, venue1, venue1, venue2, venue2, venue2]
        items = self._make_items(venues, pages)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start2, end_time=end1,
                                    day=day1)
        slot3 = Slot.objects.create(start_time=start3, end_time=end2,
                                    day=day2)

        items[0].slots.add(slot1)
        items[3].slots.add(slot1)
        items[1].slots.add(slot2)
        items[4].slots.add(slot2)
        items[2].slots.add(slot3)
        items[5].slots.add(slot3)

        c = Client()
        response = c.get('/schedule/')

        days = dict(response.context['table_days'])

        assert day1 in days
        assert day2 in days
        assert len(days[day1]) == 2
        assert len(days[day2]) == 1
        assert days[day1][0].slot.get_start_time() == start1
        assert days[day1][0].slot.end_time == start2
        assert days[day1][1].slot.get_start_time() == start2
        assert days[day1][1].slot.end_time == end1
        assert days[day2][0].slot.get_start_time() == start3
        assert days[day2][0].slot.end_time == end2

        assert len(days[day1][0].items) == 2
        assert len(days[day1][1].items) == 2
        assert len(days[day2][0].items) == 2

        assert days[day1][0].get_sorted_items()[0]['item'] == items[0]
        assert days[day1][0].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[0]['colspan'] == 1

        assert days[day2][0].get_sorted_items()[1]['item'] == items[5]
        assert days[day2][0].get_sorted_items()[1]['rowspan'] == 1
        assert days[day2][0].get_sorted_items()[1]['colspan'] == 1

    def test_col_span(self):
        """Create table with 3 venues and some interesting
           venue spanning items"""
        # Schedule is
        #         Venue 1     Venue 2   Venue3
        # 10-11   Item1       --        Item5
        # 11-12   Item2       Item3     Item4
        # 12-13   --          Item7     Item6
        # 13-14   Item8       --        --
        # 14-15   --          Item9     Item10
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue3 = Venue.objects.create(order=3, name='Venue 3')
        venue1.days.add(day1)
        venue2.days.add(day1)
        venue3.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        start3 = D.time(12, 0, 0)
        start4 = D.time(13, 0, 0)
        start5 = D.time(14, 0, 0)
        end = D.time(15, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start2, end_time=start3,
                                    day=day1)
        slot3 = Slot.objects.create(start_time=start3, end_time=start4,
                                    day=day1)
        slot4 = Slot.objects.create(start_time=start4, end_time=start5,
                                    day=day1)
        slot5 = Slot.objects.create(start_time=start5, end_time=end,
                                    day=day1)

        pages = self._make_pages(10)
        venues = [venue1, venue1, venue2, venue3, venue3, venue3,
                  venue2, venue1, venue2, venue3]
        items = self._make_items(venues, pages)

        items[0].slots.add(slot1)
        items[4].slots.add(slot1)
        items[1].slots.add(slot2)
        items[2].slots.add(slot2)
        items[3].slots.add(slot2)
        items[5].slots.add(slot3)
        items[6].slots.add(slot3)
        items[7].slots.add(slot4)
        items[8].slots.add(slot5)
        items[9].slots.add(slot5)

        c = Client()
        response = c.get('/schedule/')

        days = dict(response.context['table_days'])

        assert day1 in days
        assert len(days[day1]) == 5
        assert days[day1][0].slot.get_start_time() == start1
        assert days[day1][1].slot.get_start_time() == start2
        assert days[day1][2].slot.get_start_time() == start3
        assert days[day1][3].slot.get_start_time() == start4
        assert days[day1][4].slot.get_start_time() == start5

        assert len(days[day1][0].items) == 2
        assert len(days[day1][1].items) == 3
        assert len(days[day1][2].items) == 2
        assert len(days[day1][3].items) == 1
        assert len(days[day1][4].items) == 2

        assert days[day1][0].get_sorted_items()[0]['item'] == items[0]
        assert days[day1][0].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[0]['colspan'] == 2

        assert days[day1][0].get_sorted_items()[1]['item'] == items[4]
        assert days[day1][0].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[0]['item'] == items[1]
        assert days[day1][1].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[1]['item'] == items[2]
        assert days[day1][1].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[2]['item'] == items[3]
        assert days[day1][1].get_sorted_items()[2]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[2]['colspan'] == 1

        assert days[day1][2].get_sorted_items()[0]['item'] == items[6]
        assert days[day1][2].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][2].get_sorted_items()[0]['colspan'] == 2

        assert days[day1][2].get_sorted_items()[1]['item'] == items[5]
        assert days[day1][2].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][2].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][3].get_sorted_items()[0]['item'] == items[7]
        assert days[day1][3].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][3].get_sorted_items()[0]['colspan'] == 3

        assert days[day1][4].get_sorted_items()[0]['item'] == items[8]
        assert days[day1][4].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][4].get_sorted_items()[0]['colspan'] == 2

        assert days[day1][4].get_sorted_items()[1]['item'] == items[9]
        assert days[day1][4].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][4].get_sorted_items()[1]['colspan'] == 1

    def test_row_span(self):
        """Create a day table with multiple slot items"""
        # Schedule is
        #         Venue 1     Venue 2
        # 10-11   Item1       Item5
        # 11-12     |         Item6
        # 12-13   Item2       Item7
        # 13-14   Item3         |
        # 14-15   Item4         |
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue1.days.add(day1)
        venue2.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        start3 = D.time(12, 0, 0)
        start4 = D.time(13, 0, 0)
        start5 = D.time(14, 0, 0)
        end = D.time(15, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start2, end_time=start3,
                                    day=day1)
        slot3 = Slot.objects.create(start_time=start3, end_time=start4,
                                    day=day1)
        slot4 = Slot.objects.create(start_time=start4, end_time=start5,
                                    day=day1)
        slot5 = Slot.objects.create(start_time=start5, end_time=end,
                                    day=day1)

        pages = self._make_pages(7)
        venues = [venue1, venue1, venue1, venue1, venue2, venue2, venue2]
        items = self._make_items(venues, pages)

        items[0].slots.add(slot1)
        items[0].slots.add(slot2)
        items[4].slots.add(slot1)
        items[5].slots.add(slot2)
        items[6].slots.add(slot3)
        items[6].slots.add(slot4)
        items[6].slots.add(slot5)
        items[1].slots.add(slot3)
        items[2].slots.add(slot4)
        items[3].slots.add(slot5)

        c = Client()
        response = c.get('/schedule/')

        days = dict(response.context['table_days'])

        assert day1 in days
        assert len(days[day1]) == 5
        assert days[day1][0].slot.get_start_time() == start1
        assert days[day1][1].slot.get_start_time() == start2
        assert days[day1][4].slot.end_time == end

        assert len(days[day1][0].items) == 2
        assert len(days[day1][1].items) == 1
        assert len(days[day1][2].items) == 2
        assert len(days[day1][3].items) == 1
        assert len(days[day1][4].items) == 1

        assert days[day1][0].get_sorted_items()[0]['item'] == items[0]
        assert days[day1][0].get_sorted_items()[0]['rowspan'] == 2
        assert days[day1][0].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][0].get_sorted_items()[1]['item'] == items[4]
        assert days[day1][0].get_sorted_items()[1]['rowspan'] == 1
        assert days[day1][0].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][1].get_sorted_items()[0]['item'] == items[5]
        assert days[day1][1].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][1].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][2].get_sorted_items()[0]['item'] == items[1]
        assert days[day1][2].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][2].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][2].get_sorted_items()[1]['item'] == items[6]
        assert days[day1][2].get_sorted_items()[1]['rowspan'] == 3
        assert days[day1][2].get_sorted_items()[1]['colspan'] == 1

        assert days[day1][3].get_sorted_items()[0]['item'] == items[2]
        assert days[day1][3].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][3].get_sorted_items()[0]['colspan'] == 1

        assert days[day1][4].get_sorted_items()[0]['item'] == items[3]
        assert days[day1][4].get_sorted_items()[0]['rowspan'] == 1
        assert days[day1][4].get_sorted_items()[0]['colspan'] == 1


class ValidationTests(TestCase):

    def test_slot(self):
        """Test detection of overlapping slots"""
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        start3 = D.time(12, 0, 0)
        start35 = D.time(12, 30, 0)
        start4 = D.time(13, 0, 0)
        start45 = D.time(13, 30, 0)
        start5 = D.time(14, 0, 0)
        end = D.time(15, 0, 0)

        # Test common start time
        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start1, end_time=end, day=day1)

        overlaps = find_overlapping_slots()
        assert overlaps == set([slot1, slot2])

        slot2.start_time = start5
        slot2.save()

        # Test interleaved slot
        slot3 = Slot.objects.create(start_time=start2, end_time=start3,
                                    day=day1)
        slot4 = Slot.objects.create(start_time=start4, end_time=start5,
                                    day=day1)
        slot5 = Slot.objects.create(start_time=start35, end_time=start45,
                                    day=day1)

        overlaps = find_overlapping_slots()
        assert overlaps == set([slot4, slot5])

        # Test no overlap
        slot5.start_time = start3
        slot5.end_time = start4
        slot5.save()
        overlaps = find_overlapping_slots()
        assert len(overlaps) == 0

        # Test common end time
        slot5.end_time = start5
        slot5.save()
        overlaps = find_overlapping_slots()
        assert overlaps == set([slot4, slot5])

        # Test overlap detect with previous slot set
        slot5.start_time = None
        slot5.end_time = start5
        slot5.previous_slot = slot1
        slot5.save()
        overlaps = find_overlapping_slots()
        assert overlaps == set([slot3, slot4, slot5])

    def test_clashes(self):
        """Test that we can detect clashes correctly"""
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue1.days.add(day1)
        venue2.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        end = D.time(12, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start2, end_time=end,
                                    day=day1)

        item1 = ScheduleItem.objects.create(venue=venue1, details="Item 1")
        item2 = ScheduleItem.objects.create(venue=venue1, details="Item 2")
        # Create a simple venue/slot clash
        item1.slots.add(slot1)
        item2.slots.add(slot1)
        clashes = find_clashes()
        assert len(clashes) == 1
        pos = (venue1, slot1)
        assert pos in clashes
        assert item1 in clashes[pos]
        assert item2 in clashes[pos]
        # Create a overlapping clashes
        item2.slots.remove(slot1)
        item1.slots.add(slot2)
        item2.slots.add(slot2)
        clashes = find_clashes()
        assert len(clashes) == 1
        pos = (venue1, slot2)
        assert pos in clashes
        assert item1 in clashes[pos]
        assert item2 in clashes[pos]
        # Add a clash in a second venue
        item3 = ScheduleItem.objects.create(venue=venue2, details="Item 3")
        item4 = ScheduleItem.objects.create(venue=venue2, details="Item 4")
        item3.slots.add(slot2)
        item4.slots.add(slot2)
        clashes = find_clashes()
        assert len(clashes) == 2
        pos = (venue2, slot2)
        assert pos in clashes
        assert item3 in clashes[pos]
        assert item4 in clashes[pos]
        # Fix clashes
        item1.slots.remove(slot2)
        item3.slots.remove(slot2)
        item3.slots.add(slot1)
        clashes = find_clashes()
        assert len(clashes) == 0

    def test_validation(self):
        """Test that we detect validation errors correctly"""
        # Create a item with both a talk and a page assigned
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue1.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        end = D.time(12, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start1, end_time=end,
                                    day=day1)

        user = User.objects.create_user('john', 'best@wafer.test',
                                        'johnpassword')
        talk = Talk.objects.create(title="Test talk", status=ACCEPTED,
                                   corresponding_author_id=user.id)
        page = Page.objects.create(name="test page", slug="test")

        item1 = ScheduleItem.objects.create(venue=venue1,
                                            talk_id=talk.pk,
                                            page_id=page.pk)
        item1.slots.add(slot1)

        invalid = validate_items()
        assert set(invalid) == set([item1])

        item2 = ScheduleItem.objects.create(venue=venue1,
                                            talk_id=talk.pk)
        item2.slots.add(slot2)

        # Test talk status
        talk.status = REJECTED
        talk.save()
        invalid = validate_items()
        assert set(invalid) == set([item1, item2])

        talk.status = PENDING
        talk.save()
        invalid = validate_items()
        assert set(invalid) == set([item1, item2])

        talk.status = ACCEPTED
        talk.save()
        invalid = validate_items()
        assert set(invalid) == set([item1])

        item3 = ScheduleItem.objects.create(venue=venue1,
                                            talk_id=None, page_id=None)
        item3.slots.add(slot2)

        invalid = validate_items()
        assert set(invalid) == set([item1, item3])

    def test_duplicates(self):
        """Test that we can detect duplicates talks and pages"""
        # Final chedule is
        #       Venue 1  Venue 2
        # 10-11 Talk 1   Page 1
        # 11-12 Talk 1   Page 1
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue1.days.add(day1)
        venue2.days.add(day1)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)
        end = D.time(12, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)
        slot2 = Slot.objects.create(start_time=start1, end_time=end,
                                    day=day1)

        user = User.objects.create_user('john', 'best@wafer.test',
                                        'johnpassword')
        talk = Talk.objects.create(title="Test talk", status=ACCEPTED,
                                   corresponding_author_id=user.id)
        page1 = Page.objects.create(name="test page", slug="test")
        page2 = Page.objects.create(name="test page 2", slug="test2")

        item1 = ScheduleItem.objects.create(venue=venue1,
                                            talk_id=talk.pk)
        item1.slots.add(slot1)
        item2 = ScheduleItem.objects.create(venue=venue1,
                                            talk_id=talk.pk)
        item2.slots.add(slot2)

        duplicates = find_duplicate_schedule_items()
        assert set(duplicates) == set([item1, item2])

        item3 = ScheduleItem.objects.create(venue=venue2,
                                            page_id=page1.pk)
        item3.slots.add(slot1)
        item4 = ScheduleItem.objects.create(venue=venue2,
                                            page_id=page1.pk)
        item4.slots.add(slot2)

        duplicates = find_duplicate_schedule_items()
        assert set(duplicates) == set([item1, item2, item3, item4])

        item4.page_id = page2.pk
        item4.save()

        duplicates = find_duplicate_schedule_items()
        assert set(duplicates) == set([item1, item2])

    def test_venues(self):
        """Test that we detect venues violating the day constraints
           correctly."""
        day1 = Day.objects.create(date=D.date(2013, 9, 22))
        day2 = Day.objects.create(date=D.date(2013, 9, 23))
        venue1 = Venue.objects.create(order=1, name='Venue 1')
        venue2 = Venue.objects.create(order=2, name='Venue 2')
        venue1.days.add(day1)
        venue2.days.add(day2)

        start1 = D.time(10, 0, 0)
        start2 = D.time(11, 0, 0)

        slot1 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day1)

        page = Page.objects.create(name="test page", slug="test")

        item1 = ScheduleItem.objects.create(venue=venue1,
                                            page_id=page.pk)
        item1.slots.add(slot1)

        item2 = ScheduleItem.objects.create(venue=venue2,
                                            page_id=page.pk)
        item2.slots.add(slot1)

        venues = find_invalid_venues()
        assert set(venues) == set([venue2])
        assert set(venues[venue2]) == set([item2])

        slot2 = Slot.objects.create(start_time=start1, end_time=start2,
                                    day=day2)
        item3 = ScheduleItem.objects.create(venue=venue2, page_id=page.pk)

        item3.slots.add(slot2)
        venues = find_invalid_venues()
        assert set(venues) == set([venue2])
        assert set(venues[venue2]) == set([item2])

        item4 = ScheduleItem.objects.create(venue=venue1, page_id=page.pk)
        item5 = ScheduleItem.objects.create(venue=venue2, page_id=page.pk)

        item4.slots.add(slot2)
        item5.slots.add(slot1)
        venues = find_invalid_venues()
        assert set(venues) == set([venue1, venue2])
        assert set(venues[venue1]) == set([item4])
        assert set(venues[venue2]) == set([item2, item5])
