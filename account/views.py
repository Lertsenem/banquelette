#-*- coding: utf-8 -*-
from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import redirect, render
from django.forms import formset_factory
from django.forms.models import modelformset_factory
from django.db.models import Sum, Avg
from account.models import Account
from account.forms import AccountForm, UpdateDbForm, MonthChoiceForm, SearchForm
from account.utils import import_data 
from datetime import date, time, datetime
import calendar
import locale

import categories

locale.setlocale(locale.LC_TIME,'')
totalcat = categories.category.Category(
        "Total",
        metadata = {
            "colors": {
                "normal"   : "rgba(0,0,0,1)",
                "light"    : "rgba(0,0,0,0.6)",
                "verylight": "rgba(0,0,0,0.1)",
                }
            } )

# =============================================================================
def home(request):
    """ Page d'accueil """

    # List the 12 last months in triples
    current_year   = datetime.now().year
    current_month  = datetime.now().month
    months         = current_year * 12 + current_month - 1

    triples = [ { "year"  : ((months - i) // 12),
                  "month" : ((months - i) %  12) +1 }
                    for i in reversed(range(12))      ]

    for t in triples:
	t["month_word"] = date( t["year"],
                                t["month"],
                                1           ).strftime('%B').capitalize()

    # Get the FIRST_LEVEL_CATEGORIES
    first_level_categories = categories.FIRST_LEVEL_CATEGORIES

    # 1e partie : graph des dépenses de l'annee
    total_by_month = {}

    # Iterate over each of the 12 last months
    for t in triples :
        account_filter_year  = Account.objects  \
                .filter( date__year=t["year"] )
        account_filter_month = account_filter_year \
                .filter( date__month=t["month"] )

        # Iterate over each category
        for k,cat in first_level_categories.items():
            # Append this month total to the total_by_month[category] list
            try:
                this_month_total = account_filter_month      \
                        .filter(category__startswith = k) \
                        .aggregate( Sum('expense') )         \
                        ['expense__sum']
                this_month_total = abs(int( this_month_total ))

            except:
                this_month_total = 0

            # (Try to append, if it doesn't work, it's because the key does not
            # exist yet).
            try:
                total_by_month[cat].append(this_month_total)
            except KeyError:
                total_by_month[cat] = [ this_month_total ]


        # We finished looping over the first-level categories, let's add a
        # 'Total' category:
        try:
            this_month_total = account_filter_month      \
                    .aggregate( Sum('expense') )         \
                    ['expense__sum']
            this_month_total = abs(int( this_month_total ))

        except:
            this_month_total = 0

        try:
            total_by_month[totalcat].append(this_month_total)
        except:
            total_by_month[totalcat] = [this_month_total]

    # And done!
    return render(request, 'account/accueil.html', locals())

# =============================================================================
def statistics(request):
    """ Statistics """

    # Get the FIRST_LEVEL_CATEGORIES
    first_level_categories = categories.FIRST_LEVEL_CATEGORIES

    first_year    = 2015
    current_year  = datetime.now().year
    total_by_year = {}
    average_by_year = {}
    for i in range(first_year, current_year+1):
        total_by_year[i] = {}
        average_by_year[i] = {}

    for y in total_by_year.keys():
        account_filter_year  = Account.objects  \
                .filter( date__year=y )

        # Iterate over each category
        for k,cat in first_level_categories.items():
            # Append this total to the total_by_year[year][category] list
            this_category_total = account_filter_year    \
                    .filter(category__startswith = k)    \
                    .aggregate( Sum('expense') )         \
                    ['expense__sum']
            if this_category_total is None:
                this_category_total = 0
            total_by_year[y][cat] = this_category_total 

            # Append this average to the average_by_year[year][category] list
            this_category_average = account_filter_year    \
                    .filter(category__startswith = k)    \
                    .aggregate( Avg('expense') )         \
                    ['expense__avg']
            if this_category_average is None:
                this_category_average = 0
            average_by_year[y][cat] = this_category_average 
    
        # We finished looping over the first-level categories, let's add a
        # 'Total' category:
        this_category_total = account_filter_year    \
                .aggregate( Sum('expense') )         \
                ['expense__sum']
        if this_category_total is None:
            this_category_total = 0
        total_by_year[y][totalcat] = this_category_total

        this_category_average = account_filter_year    \
                .aggregate( Avg('expense') )         \
                ['expense__avg']
        if this_category_average is None:
            this_category_average = 0
        average_by_year[y][totalcat] = this_category_average
    
    return render(request, 'account/statistics.html', locals())

# =============================================================================
def search(request):
    """ Search """
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            # Get all objects (transactions) order them by date.
            account_objects = Account.objects    \
                .order_by('date')
            
            if form.cleaned_data['date_start'] is not None:
                date_start = form.cleaned_data['date_start']
                account_objects = account_objects.filter(date__gte = date_start)
            if form.cleaned_data['date_end'] is not None:
                date_end = form.cleaned_data['date_end']
                account_objects = account_objects.filter(date__gte = date_end)
            if form.cleaned_data['category'] is not None:
                category = form.cleaned_data['category']
                account_objects = account_objects.filter(category__startswith = category)
            if form.cleaned_data['bank'] is not None:
                bank = form.cleaned_data['bank']
                account_objects = account_objects.filter(bank__exact = bank)
            if form.cleaned_data['description'] is not None:
                description = form.cleaned_data['description']
                account_objects = account_objects.filter(description__contains = description) 
            
            # Get the first-level categories (those without a parent category)
            first_level_categories ={} 
            for k,cat in categories.FIRST_LEVEL_CATEGORIES.items():
                first_level_categories[cat] = 0
            
            # Si count_comment != 0 une colone est ajouté dans template month.html
            count_comment = account_objects.exclude(comment__exact="").count()
            if count_comment == 0 :
                comment = False
            else: 
                comment = True

            # For each first-level category, we are going to find the relevant objects
            # (transactions) and sum them.
            for c in first_level_categories:

                # Sum the relevant account object 'expense' property
                category_sum = account_objects               \
                        .filter(category__startswith = c) \
                        .aggregate(Sum('expense'))

                # Save the result
                if category_sum['expense__sum'] is not None:
                    first_level_categories[c] = category_sum['expense__sum']

            # We got the sum of expenses for each category, now we can add a 'Total'
            # category:
            first_level_categories["Total"] = sum( first_level_categories.values() )

    else:
        form=SearchForm()


    return render(request, 'account/search.html', locals())


# =============================================================================
def release(request):
    """ Release """
    return render(request, 'account/release.html')
    

# =============================================================================
def month_view(request, year, month, category=None):
    """ Résumé par mois """
    if not year or not month:
        raise Http404

    month_word = date(int(year), int(month), 1).strftime('%B').capitalize()
    first_level_categories ={} 

    # Get all objects (transactions) with the right date (year+month) and order
    # them by date.
    account_objects = Account.objects        \
            .order_by('date')                \
            .filter(date__year = int(year) ) \
            .filter(date__month= int(month))

    # Get the first-level categories (those without a parent category)
    for k,cat in categories.FIRST_LEVEL_CATEGORIES.items():
        first_level_categories[cat] = 0
    
    if category is not None:
        if category in first_level_categories:
            account_objects = account_objects.filter(category__exact=category) 
        else:
            raise Http404

    # Si count_comment != 0 une colone est ajouté dans template month.html
    count_comment = account_objects.exclude(comment__exact="").count()
    if count_comment == 0 :
        comment = False
    else: 
        comment = True

    # For each first-level category, we are going to find the relevant objects
    # (transactions) and sum them.
    for c in first_level_categories:

        # Sum the relevant account object 'expense' property
        category_sum = account_objects               \
                .filter(category__startswith = c) \
                .aggregate(Sum('expense'))

        # Save the result
        if category_sum['expense__sum'] is not None:
            first_level_categories[c] = category_sum['expense__sum']

    # We got the sum of expenses for each category, now we can add a 'Total'
    # category:
    first_level_categories["Total"] = sum( first_level_categories.values() )

    # And done!
    return render(request, 'account/month.html', locals())

# =============================================================================
def month_choice(request):
    """ Choix du mois """
    title = "Choix du mois"
    if request.method == 'POST':
        form = MonthChoiceForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            month = form.cleaned_data['month']
            return redirect(db_modify, year=year, month=month)
    else:
        form=MonthChoiceForm()

    return render(request, 'account/month_choice.html', locals())
    
    
def db_modify(request, year=None, month=None):
    """ Modification par mois ou les non check"""
    # definition des variables
    if year == None:
        title = "Dépenses non validées"
        account_all = Account.objects.filter(check__exact=False)
    else:
        month_word = date(int(year), int(month), 1).strftime('%B').capitalize().decode('utf-8')
        title = ''.join([month_word, " ", year])
        account_all = Account.objects.filter(date__year=int(year)).filter(date__month=int(month))

    AccountFormSet = modelformset_factory(Account, fields=('date', 'description', 'category', 'expense', 'halve', 'bank', 'check', 'comment'), extra=0, can_delete=True)
    if request.method == 'POST':  # S'il s'agit d'une requête POST
        formset = AccountFormSet(request.POST)
        if formset.is_valid(): # Nous vérifions que les données envoyées sont valides
           formset.save()
           if year == None:
               return redirect(home)
           return redirect(month_view, year=year, month=month)

    else: # Si ce n'est pas du POST, c'est probablement une requête GET
        formset = AccountFormSet(queryset=account_all)
    return render(request, 'account/db_modify.html', locals())

	
def db_add(request):
    """ Ajout d'entrées manuelles """
    title = "Ajout d'entrées manuelles"
    n = 5
    AccountFormSet = modelformset_factory(Account, fields=('date', 'description', 'category', 'expense', 'halve', 'bank', 'check', 'comment'), extra=n, can_delete=True)
    if request.method == 'POST':  # S'il s'agit d'une requête POST
        formset = AccountFormSet(request.POST)
        if formset.is_valid(): 
            formset.save()
            return redirect(home)

    else: # Si ce n'est pas du POST, c'est probablement une requête GET
        formset = AccountFormSet(queryset=Account.objects.none())

    return render(request, 'account/db_add.html', locals())
    

def db_update(request):
    """ Mise à jour de la base de donnée avec de nouvelles données """
    if request.method == 'POST':
        form = UpdateDbForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data['data']
            bank = form.cleaned_data['bank']
            # Analyse des données stockées dans une liste
            import_data(data, bank)
            return redirect(db_modify)
    else:
        form=UpdateDbForm()

    return render(request, 'account/db_update.html', locals())
