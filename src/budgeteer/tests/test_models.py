"""
Unit tests for the budgeteer main app models.
"""

import datetime
import random
import string
import calendar
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

import budgeteer.models as models

#pylint: disable=missing-function-docstring
#pylint: disable=missing-class-docstring

class CategoryTests(TestCase):

    def test_name_save(self):
        category = models.Category()
        category.name = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        category.full_clean()
        category.save()

        category_from_db = models.Category.objects.get(pk=category.pk)

        self.assertEqual(category.name, category_from_db.name)

    def test_name_max_length_not_ok(self):
        category = models.Category()
        category.name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))
        with self.assertRaises(ValidationError):
            category.full_clean()

class SheetTests(TestCase):

    def test_month_save(self):
        expected_month = random.randint(1, 12)

        sheet = models.Sheet()
        sheet.month = expected_month
        sheet.year = 1
        sheet.full_clean()
        sheet.save()

        sheet_from_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(expected_month, sheet_from_db.month)

    def test_month_allowed_values(self):
        for month in range(1, 12):
            sheet = models.Sheet()
            sheet.month = month
            sheet.year = 1

            try:
                sheet.full_clean()
            except ValidationError:
                self.fail(f"Month {month} failed to validate")

    def test_month_min_value(self):
        sheet = models.Sheet()
        sheet.year = 1
        sheet.month = 0
        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_month_max_value(self):
        sheet = models.Sheet()
        sheet.year = 1
        sheet.month = 13
        with self.assertRaises(ValidationError):
            sheet.full_clean()

    def test_year_save(self):
        expected_year = random.randint(1980, 2100)

        sheet = models.Sheet()
        sheet.month = 1
        sheet.year = expected_year
        sheet.full_clean()
        sheet.save()

        sheet_from_db = models.Sheet.objects.get(pk=sheet.pk)

        self.assertEqual(expected_year, sheet_from_db.year)

    def test_year_no_negative_values(self):
        sheet = models.Sheet()
        sheet.month = 1
        sheet.year = -1

        with self.assertRaises(IntegrityError):
            sheet.save()

    def test_combination_unique(self):
        sheet_1 = models.Sheet(month=1, year=1)
        sheet_1.full_clean()
        sheet_1.save()

        sheet_2 = models.Sheet(month=1, year=1)
        with self.assertRaises(ValidationError):
            sheet_2.full_clean()

    def test_get_transactions(self):
        sheet = models.Sheet(month=2, year=2020)
        sheet.save()

        transaction_to_expect_1 = _create_transaction(2, 2020)
        transaction_to_expect_2 = _create_transaction(2, 2020)
        transaction_to_expect_3 = _create_transaction(2, 2020)

        _create_transaction(2, 2019)
        _create_transaction(2, 2021)
        _create_transaction(1, 2020)
        _create_transaction(3, 2020)
        _create_transaction(3, 2021)
        _create_transaction(1, 2019)
        _create_transaction(3, 2019)
        _create_transaction(1, 2021)

        expected_transactions = [transaction_to_expect_1,
                                 transaction_to_expect_2,
                                 transaction_to_expect_3]
        actual_transactions = list(sheet.transactions)

        self.assertCountEqual(expected_transactions, actual_transactions)

class SheetEntryTest(TestCase):

    def setUp(self):
        self.sheet = models.Sheet(month=1, year=1)
        self.sheet.save()

        self.category = models.Category(name="Test category")
        self.category.save()

    def tearDown(self):
        self.sheet.delete()
        self.category.delete()

    def test_entry_save(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(entry, entry_in_db)

    def test_foreign_key_sheet(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(self.sheet, entry_in_db.sheet)

    def test_foreign_key_category(self):
        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=0)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(self.category, entry_in_db.category)

    def test_sheet_cascade(self):
        sheet = models.Sheet(month=2, year=1)
        sheet.save()

        entry = models.SheetEntry(sheet=sheet, category=self.category, value=0)
        entry.save()

        sheet.delete()

        actual_count = models.SheetEntry.objects.filter(pk=entry.pk).count()

        self.assertEqual(0, actual_count)

    def test_category_cascade(self):
        category = models.Category(name="Test")
        category.save()

        entry = models.SheetEntry(sheet=self.sheet, category=category, value=0)
        entry.save()

        category.delete()

        actual_count = models.SheetEntry.objects.filter(pk=entry.pk).count()

        self.assertEqual(0, actual_count)

    def test_value_save(self):
        expected_value = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)
        entry.save()

        entry_in_db = models.SheetEntry.objects.get(pk=entry.pk)

        self.assertEqual(expected_value, entry_in_db.value)

    def test_value_max_digits(self):
        expected_value = Decimal('12345678901.23')

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)

        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_value_decimal_places(self):
        expected_value = Decimal('123456789.123')

        entry = models.SheetEntry(sheet=self.sheet, category=self.category, value=expected_value)

        with self.assertRaises(ValidationError):
            entry.full_clean()

class AccountTest(TestCase):

    def test_name_save(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=200))

        account = models.Account()
        account.name = expected_name
        account.balance = Decimal(0)
        account.full_clean()
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_name, account_in_db.name)

    def test_name_max_value(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))

        account = models.Account()
        account.name = expected_name
        account.balanace = 0

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_balance(self):
        expected_balance = (Decimal(random.uniform(-999999999.99, 999999999.99))
                            .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = expected_balance
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_balance, account_in_db.balance)

    def test_balance_max_digits(self):
        balance = Decimal('12345678901.23')

        account = models.Account(name="Test account", balance=balance)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_balance_decimal_places(self):
        balance = Decimal('123456789.123')

        account = models.Account(name="Test account", balance=balance)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_total_no_transactions(self):
        expected_total = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = expected_total
        account.save()

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_total, account_in_db.total)

    def test_total_only_unlocked_transactions(self):
        starting_balance = (Decimal(random.uniform(-9999.99, 9999.99))
                            .quantize(Decimal('.01')))

        account = models.Account()
        account.balance = starting_balance
        account.save()

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        transactions = ([_create_transaction(tomorrow.month, tomorrow.year, account)
                         for _ in range(1)])

        expected_total = ((starting_balance + sum(Decimal(t.value) for t in transactions))
                          .quantize(Decimal('.01')))

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_total, account_in_db.total)

    def test_total_ignore_locked_transaction(self):
        pass

    def test_total_ignore_other_accounts(self):
        #pylint: disable=unused-variable
        starting_balance = Decimal(random.uniform(-9999.99, 9999.99)).quantize(Decimal('.01'))

        account = models.Account()
        account.balance = starting_balance
        account.save()

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        transactions = ([_create_transaction(tomorrow.month, tomorrow.year, account)
                         for _ in range(1)])
        unexpected_transactions = [(_create_transaction(tomorrow.month,
                                                        tomorrow.year,
                                                        account,
                                                        locked=True)
                                    for _ in range(1))]

        expected_total = ((starting_balance + sum(Decimal(t.value) for t in transactions))
                          .quantize(Decimal('.01')))

        account_in_db = models.Account.objects.get(pk=account.pk)

        self.assertEqual(expected_total, account_in_db.total)

class TransactionTest(TestCase):

    def setUp(self):
        self.category = models.Category(name="Test")
        self.category.save()
        self.account = models.Account(name="Test", balance=Decimal(0))
        self.account.save()

    def tearDown(self):
        models.Transaction.objects.all().delete()
        self.account.delete()
        self.category.delete()

    def test_partner_save(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=200))

        transaction = models.Transaction()
        transaction.partner = expected_name
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_name, transaction_in_db.partner)

    def test_partner_max_length(self):
        expected_name = ''.join(random.choices(string.ascii_letters + string.digits, k=201))

        transaction = models.Transaction()
        transaction.partner = expected_name
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_date_save(self):
        expected_date = datetime.date(random.randrange(1980, 2100),
                                      random.randrange(1, 12),
                                      random.randrange(1, 28))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = expected_date
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_date,
                         transaction_in_db.date)

    def test_value_save(self):
        expected_value = (Decimal(random.uniform(-999999999.99, 999999999.99))
                          .quantize(Decimal('.01')))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_value, transaction_in_db.value)

    def test_value_max_digits(self):
        expected_value = Decimal('12345678901.23')

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_value_decimal_places(self):
        expected_value = Decimal('123456789.123')

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = expected_value
        transaction.category = self.category
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_category(self):
        expected_category = models.Category(name="Expected category")
        expected_category.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = expected_category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_category, transaction_in_db.category)

    def test_category_must_be_set(self):

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = None
        transaction.account = self.account

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_category_prevent_deletion(self):
        category = models.Category(name="Expected category")
        category.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        with self.assertRaises(ProtectedError):
            category.delete()

    def test_account(self):
        expected_account = models.Account(name="Expected account", balance=Decimal(0))
        expected_account.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = expected_account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertEqual(expected_account, transaction_in_db.account)

    def test_account_must_be_net(self):

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = None

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_account_prevent_deletion(self):
        account = models.Account(name="Expected account", balance=Decimal(0))
        account.save()

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = account
        transaction.full_clean()
        transaction.save()

        with self.assertRaises(ProtectedError):
            account.delete()

    def test_locked(self):
        expected_lock = bool(random.getrandbits(1))

        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.locked = expected_lock
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.full_clean()
        self.assertEqual(expected_lock, transaction_in_db.locked)

    def test_locked_default_false(self):
        transaction = models.Transaction()
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        self.assertFalse(transaction_in_db.locked)

    def test_locked_no_change_to_partner(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.partner = "b"

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_date(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.date = datetime.date.today() + datetime.timedelta(days=1)

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_value(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.value = 1

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_category(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        category = models.Category(name="Test category")
        category.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.category = category

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

    def test_locked_no_change_to_account(self):
        transaction = models.Transaction()
        transaction.locked = True
        transaction.partner = "a"
        transaction.date = datetime.date.today()
        transaction.value = 0
        transaction.category = self.category
        transaction.account = self.account
        transaction.full_clean()
        transaction.save()

        account = models.Account(name="Test account", balance=0)
        account.save()

        transaction_in_db = models.Transaction.objects.get(pk=transaction.pk)

        transaction_in_db.account = account

        with self.assertRaises(ValidationError):
            transaction_in_db.full_clean()

def _create_transaction(month, year, account=None, locked=False) -> models.Transaction:
    category = models.Category(name="Test category")
    category.save()
    if account is None:
        account = models.Account(name="Test account", balance=Decimal(0))
        account.save()

    transaction = models.Transaction()
    transaction.category = category
    transaction.account = account
    transaction.value = Decimal(random.uniform(-999.99, 999.99))
    transaction.partner = "Test partner"
    transaction.locked = locked
    transaction.date = _random_day_in_month(month, year)

    transaction.save()
    return transaction

def _random_day_in_month(month, year):
    dates = calendar.Calendar().itermonthdates(year, month)
    return random.choice([date for date in dates if date.month == month])