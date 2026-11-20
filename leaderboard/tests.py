from datetime import date

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CATEGORY_DEFINITIONS, Member, ScoreCategory, ScoreEntry
from .services import build_rankings


class RankingSystemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(
            username="clubadmin", email="admin@example.test", password="test-password-123"
        )
        cls.categories = {category.code: category for category in ScoreCategory.objects.all()}

    def member(self, name="Asha Rao", usn="SPK001", semester=3, team="Web"):
        return Member.objects.create(full_name=name, usn=usn, semester=semester, branch="CSE", team_name=team)

    def award(self, member, category_code, points, *, day=None, reason="Club contribution"):
        return ScoreEntry.objects.create(
            member=member,
            category=self.categories[category_code],
            points=points,
            reason=reason,
            awarded_by=self.actor,
            date_awarded=day or timezone.localdate(),
        )

    def test_member_creation(self):
        member = self.member()
        self.assertEqual(Member.objects.get(usn="SPK001"), member)
        self.assertTrue(member.is_active)

    def test_six_default_categories_are_created(self):
        self.assertEqual(ScoreCategory.objects.count(), 6)
        self.assertEqual(set(self.categories), {code for code, _, _ in CATEGORY_DEFINITIONS})

    def test_positive_point_entry_adds_to_category_total(self):
        member = self.member()
        self.award(member, "teaching", 50)
        row = build_rankings()[0]
        self.assertEqual(row["scores"]["teaching"], 50)

    def test_negative_discipline_entry_deducts_points(self):
        member = self.member()
        self.award(member, "discipline", -20, reason="Missed assigned responsibility")
        self.assertEqual(build_rankings()[0]["scores"]["discipline"], -20)

    def test_total_is_the_sum_of_all_six_categories(self):
        member = self.member()
        for code, amount in {
            "teaching": 50,
            "projects": 100,
            "attendance": 10,
            "discipline": -20,
            "events": 200,
            "skills": 75,
        }.items():
            self.award(member, code, amount)
        row = build_rankings()[0]
        self.assertEqual(row["total"], 415)
        self.assertEqual(row["total"], sum(row["scores"].values()))

    def test_points_are_not_limited_to_sqlite_integer_range(self):
        member = self.member()
        huge = 10**120 + 87654321
        self.award(member, "skills", huge)
        saved = ScoreEntry.objects.get(member=member)
        self.assertEqual(saved.points, huge)
        self.assertEqual(build_rankings()[0]["total"], huge)

    def test_ranking_order_uses_combined_score(self):
        first = self.member("First", "SPK001")
        second = self.member("Second", "SPK002")
        third = self.member("Third", "SPK003")
        self.award(first, "teaching", 120)
        self.award(second, "projects", 250)
        self.award(third, "discipline", -1)
        self.assertEqual([row["member"] for row in build_rankings()], [second, first, third])

    def test_tied_scores_use_documented_category_and_usn_order(self):
        higher_skill = self.member("Skill", "SPK002")
        earlier_usn = self.member("USN", "SPK001")
        self.award(higher_skill, "skills", 10)
        self.award(earlier_usn, "projects", 10)
        rows = build_rankings()
        self.assertEqual([row["member"] for row in rows], [higher_skill, earlier_usn])
        self.assertEqual([row["rank"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["total"], rows[1]["total"])

    def test_zero_point_members_are_included(self):
        first = self.member("Zero One", "SPK001")
        second = self.member("Zero Two", "SPK002")
        rows = build_rankings()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["total"] for row in rows], [0, 0])
        self.assertEqual({row["member"].pk for row in rows}, {first.pk, second.pk})

    def test_monthly_ranking_only_counts_selected_month(self):
        member = self.member()
        today = timezone.localdate()
        self.award(member, "skills", 11, day=today)
        previous_year = date(today.year - 1 if today.year > 1 else today.year + 1, today.month, 1)
        self.award(member, "skills", 90, day=previous_year)
        current_month = today.strftime("%Y-%m")
        self.assertEqual(build_rankings(mode="monthly", month=current_month)[0]["total"], 11)

    def test_overall_ranking_keeps_cumulative_points(self):
        member = self.member()
        today = timezone.localdate()
        prior = date(today.year - 1 if today.year > 1 else today.year + 1, today.month, 1)
        self.award(member, "projects", 30, day=today)
        self.award(member, "projects", 70, day=prior)
        self.assertEqual(build_rankings()[0]["total"], 100)

    def test_admin_requires_staff_access_and_score_history_is_read_only(self):
        add_url = reverse("admin:leaderboard_scoreentry_add")
        self.assertEqual(self.client.get(add_url).status_code, 302)

        regular_staff = get_user_model().objects.create_user(username="staff", password="test-password-123", is_staff=True)
        self.client.force_login(regular_staff)
        self.assertEqual(self.client.get(add_url).status_code, 403)

        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(add_url).status_code, 200)
        member = self.member()
        entry = self.award(member, "attendance", 5)
        change_url = reverse("admin:leaderboard_scoreentry_change", args=(entry.pk,))
        self.assertEqual(self.client.get(change_url).status_code, 200)
        admin_request = self.request_factory().get(change_url)
        admin_request.user = self.actor
        self.assertFalse(admin.site._registry[ScoreEntry].has_delete_permission(admin_request, entry))

    def test_admin_rejects_score_changes_even_if_readonly_fields_are_posted(self):
        member = self.member()
        entry = self.award(member, "skills", 12, reason="Original award")
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("admin:leaderboard_scoreentry_change", args=(entry.pk,)),
            {
                "member": member.pk,
                "category": self.categories["skills"].pk,
                "points": "999999",
                "reason": "Forged edit",
                "date_awarded": timezone.localdate().isoformat(),
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.points, 12)
        self.assertEqual(entry.reason, "Original award")

    def test_admin_score_creation_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        add_url = reverse("admin:leaderboard_scoreentry_add")
        self.assertEqual(client.get(add_url).status_code, 200)
        response = client.post(add_url, {"reason": "CSRF check"})
        self.assertEqual(response.status_code, 403)

    def test_admin_login_throttles_repeated_bad_passwords(self):
        login_url = reverse("admin:login")
        response = None
        for _ in range(5):
            response = self.client.post(
                login_url,
                {"username": "clubadmin", "password": "incorrect-password"},
            )
        self.assertEqual(response.status_code, 429)
        locked_response = self.client.post(
            login_url,
            {"username": "clubadmin", "password": "test-password-123"},
        )
        self.assertEqual(locked_response.status_code, 429)

    def test_admin_login_accepts_valid_credentials(self):
        response = self.client.post(
            reverse("admin:login"),
            {"username": "clubadmin", "password": "test-password-123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.actor.pk))

    def test_public_and_admin_text_fields_are_escaped(self):
        attack_name = "<script>alert(1)</script>"
        attack_team = "<img src=x onerror=alert(1)>"
        member = self.member(attack_name, "SPK099", team=attack_team)
        self.award(member, "skills", 1, reason=attack_name)

        public_response = self.client.get("/")
        self.assertContains(public_response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertContains(public_response, "&lt;img src=x onerror=alert(1)&gt;")
        self.assertNotContains(public_response, attack_name)

        self.client.force_login(self.actor)
        admin_response = self.client.get(reverse("admin:leaderboard_scoreentry_changelist"))
        self.assertContains(admin_response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(admin_response, attack_name)

    def test_public_page_links_to_existing_frontend_assets(self):
        response = self.client.get("/")
        self.assertContains(response, "/static/css/style.css")
        self.assertContains(response, "/static/js/script.js")
        self.assertTrue(finders.find("css/style.css"))
        self.assertTrue(finders.find("js/script.js"))

    def test_unapproved_host_header_is_rejected(self):
        client = Client(raise_request_exception=False)
        response = client.get("/", HTTP_HOST="attacker.example")
        self.assertEqual(response.status_code, 400)

    def test_api_routes_are_not_exposed(self):
        self.assertEqual(self.client.get("/api/").status_code, 404)

    def test_admin_can_award_and_attribute_an_unlimited_score_transaction(self):
        member = self.member()
        amount = "9" * 150
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("admin:leaderboard_scoreentry_add"),
            {
                "member": member.pk,
                "category": self.categories["skills"].pk,
                "points": amount,
                "reason": "Completed an advanced technical learning milestone",
                "date_awarded": timezone.localdate().isoformat(),
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302, response.content.decode())
        entry = ScoreEntry.objects.get(member=member)
        self.assertEqual(entry.points, int(amount))
        self.assertEqual(entry.awarded_by, self.actor)

    def test_search_and_filters_use_server_rendered_member_records(self):
        matching = self.member("Mira Rao", "SPK021", semester=4, team="AI")
        self.member("Ravi Das", "SPK022", semester=4, team="Web")
        self.member("Mira Patel", "SPK023", semester=2, team="AI")
        self.award(matching, "projects", 75)
        response = self.client.get("/", {"q": "Mira", "semester": "4", "team": "AI"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "Mira Rao")
        self.assertNotContains(response, "Ravi Das")
        self.assertNotContains(response, "Mira Patel")
        self.assertContains(response, "75")

    def test_usn_is_private_by_default_on_public_page(self):
        self.member("Privacy Test", "SECRET-USN")
        response = self.client.get("/")
        self.assertNotContains(response, "SECRET-USN")
        self.assertContains(response, "aria-label=\"USN not publicly shared\"")

    def test_history_is_preserved_as_new_adjustment_entry(self):
        member = self.member()
        original = self.award(member, "discipline", -8, reason="Late arrival")
        correction = self.award(member, "discipline", 8, reason="Correction: attendance was recorded incorrectly")
        self.assertEqual(ScoreEntry.objects.filter(member=member).count(), 2)
        self.assertTrue(ScoreEntry.objects.filter(pk=original.pk).exists())
        self.assertEqual(build_rankings()[0]["total"], 0)
        self.assertEqual(correction.awarded_by, self.actor)

    def test_inactive_members_are_not_publicly_ranked(self):
        active = self.member("Active", "SPK001")
        inactive = self.member("Inactive", "SPK002")
        inactive.is_active = False
        inactive.save(update_fields=("is_active",))
        self.assertEqual([row["member"] for row in build_rankings()], [active])
        self.assertEqual(len(build_rankings(include_inactive=True)), 2)

    @staticmethod
    def request_factory():
        from django.test import RequestFactory

        return RequestFactory()
