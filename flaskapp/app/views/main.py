from flask import Blueprint, render_template, Markup, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from sqlalchemy import extract
import datetime, pytz, calendar, json, locale

# Forms
from app.forms import FiltersForm, NewOperationForm, UserSettingsForm, AddCurrencyForm, ChangeCurrencyForm

# Models
from app.models import User, UserConfiguration, Operation, OperationType, Month, Saving, Currency

# Database
from app.extensions import db

main = Blueprint('main', __name__)

operationTypeIcons = [
    "fas fa-tshirt", "fas fa-hamburger", "fas fa-file-invoice-dollar", "fas fa-gift",
    "fas fa-laptop", "fas fa-couch", "fas fa-gas-pump", "fas fa-money-check-alt", "fas fa-eye",
    "fas fa-bath", "fas fa-bus", "fas fa-suitcase-rolling", "fas fa-gamepad", "fas fa-list-ul", "fas fa-money-bill-wave", "fab fa-untappd", "fas fa-university", "fas fa-flag",
    "fas fa-building"
]

operationTypeIconsColor = [
    "tshirt", "hamburger", "file-invoice-dollar", "gift", "laptop",
    "couch", "gas-pump", "money-check", "eye", "bath", "bus", "suitcase-rolling", "gamepad", "list-ul", "money-bill-wave", "untappd", "university", "flag", "building"
]

@main.route('/')
@main.route('/home')
def home():
    if ( current_user.is_authenticated ):
        return redirect(url_for('main.dashboard'))
    else:
        return render_template('home.html')

@main.route('/home/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    today = datetime.datetime.today()
    today_localize = today.astimezone(pytz.timezone('America/Buenos_Aires'))

    if request.method == 'GET':
        # Fill Filter Fields with current date and None for Operation_Type
        month = today_localize.month
        year = today_localize.year
        filter_month_id = month
        filter_year_id = 0
        filter_type_id = 0
        
        # Check for cookies values from preview dashboard filter POST
        if request.args.get('messages') is not None:
            messages = request.args['messages']
            messages=json.loads(messages)

            if messages.get('month_id') is not None:
                filter_month_id = messages.get('month_id')

            if messages.get('year_id') is not None:
                filter_year_id = messages.get('year_id')
            
            if messages.get('type_id') is not None:
                filter_type_id = messages.get('type_id')

        filterForm = FiltersForm(month_id=filter_month_id, year_id=filter_year_id, type_id=filter_type_id)
        
        # Get User Data
        user = User.query.filter_by(username=current_user.username).first()

        # Get User Configuration
        userConfig = UserConfiguration.query.filter_by(user_id=user.id).first()

        # Set User Settings to UserSettingsForm
        userSettingsForm = UserSettingsForm(spend_limit=userConfig.spend_limit, warning_percent=userConfig.warning_percent, hide_amounts=userConfig.hide_amounts, user_id=userConfig.user_id)

        # Set hidden user_id to all the Forms in the Dashboard View
        newOperationForm = NewOperationForm(user_id=user.id)
        editOperationForm = NewOperationForm(user_id=user.id)
        addCurrencyForm = AddCurrencyForm(user_id=user.id)
        changeCurrencyForm = ChangeCurrencyForm(user_id=user.id)

        # Set DataTypes to all the Selects of EveryForm in Dashboard View
        filterForm.month_id.choices = [(m.id, m.description) for m in Month.query.order_by('id')]
        filterForm.month_id.choices.insert(0, ('0', 'Todos'))

        yearList = list(range(year, year - 21, -1))
        filterForm.year_id.choices = [(index, description) for index, description in enumerate(yearList, start=0)]
        
        filterForm.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]
        filterForm.type_id.choices.insert(0, ('0', 'Todos'))

        newOperationForm.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]
        editOperationForm.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]

        # Set Left Currencies for user_id to the addCurrencyForm and newOperationForm
        userCurrencies = Saving.query.filter_by(user_id=user.id).with_entities(Saving.currency_id)
        leftCurrencies = Currency.query.filter(Currency.id.notin_(userCurrencies))
        haveCurrencies = Currency.query.filter(Currency.id.in_(userCurrencies))

        addCurrencyForm.currency_id.choices = [(c.id, c.description) for c in leftCurrencies]
        leftCurrencies = leftCurrencies.all()

        newOperationForm.currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
        editOperationForm.currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
        changeCurrencyForm.origin_currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
        changeCurrencyForm.destination_currency_id.choices = [(c.id, c.description) for c in haveCurrencies]

        haveCurrencies = haveCurrencies.all()
        userCurrencies = userCurrencies.all()

        # Get Operation (Gained and Spend) by filter
        operations = None
        yearFilter = year - filter_year_id
        if filter_month_id != 0 and filter_type_id != 0:
            formatDateStart = datetime.datetime(yearFilter, filter_month_id, 1)
            formatDateEnd = datetime.datetime(yearFilter, filter_month_id, calendar.monthrange(yearFilter, filter_month_id)[1])
            operations = Operation.query.filter(Operation.user_id == user.id, Operation.date <= formatDateEnd, Operation.date >= formatDateStart, Operation.type_id == filter_type_id)
        elif filter_month_id != 0 and filter_type_id == 0:
            formatDateStart = datetime.datetime(yearFilter, filter_month_id, 1)
            formatDateEnd = datetime.datetime(yearFilter, filter_month_id, calendar.monthrange(yearFilter, filter_month_id)[1])
            operations = Operation.query.filter(Operation.user_id == user.id, Operation.date <= formatDateEnd, Operation.date >= formatDateStart)
        elif filter_month_id == 0 and filter_type_id != 0:
            operations = Operation.query.filter(Operation.user_id == user.id, Operation.type_id == filter_type_id, extract('year', Operation.date) == yearFilter)
        else:
            operations = Operation.query.filter(Operation.user_id == user.id, extract('year', Operation.date) == yearFilter)

        # Calculate gainedAmount ( SUM(user.operations.amount type == Ganancia ))
        gainedAmount = sum(operation.amount for operation in operations if operation.type_id == 15)
        
        # Calculate SpendAmount ( gainedAmount - SUM(user.operations.amount type != Ganancia ))
        spendAmount = sum(operation.amount for operation in operations if operation.type_id != 15 and operation.type_id != 17)
            
        # Load Operation Types
        operationTypes = OperationType.query.order_by(OperationType.id).all()

        # Calculate Operation Type Statistics
        # Get total amounts of all User's operation types loaded
        userOperationTypesAmounts = [ (op.id, round(sum(operation.amount for operation in operations if operation.type_id == op.id ), 2)) for op in operationTypes if op.id != 15 ]

        #Calculate 
        operationStatistics = [ (operationTypes[uop[0]-1], uop[1], round((uop[1] * 100) / spendAmount if spendAmount > 0 else 0 , 2)) for uop in userOperationTypesAmounts ]

        # Format All the Amounts to Currency
        formattedTotalAmount = "$ {:,.2f}".format(gainedAmount)
        formattedSpendAmount = "$ {:,.2f}".format(spendAmount)
        formattedAvailableAmount = "$ {:,.2f}".format(gainedAmount - spendAmount)

        # Calculate Spend Amount Badge Status Color
        spendAmountStatusColor = 'badge-success'
        if userConfig.warning_percent is None:
            userConfig.warning_percent = 25

        if spendAmount >= (gainedAmount * ( userConfig.warning_percent / 100)) and spendAmount < gainedAmount:
            spendAmountStatusColor = 'badge-warning'
        elif spendAmount >= gainedAmount:
            spendAmountStatusColor = 'badge-danger'

        # Load all Currencies
        currencies = Currency.query.order_by(Currency.id).all()

        # Get all the Savings
        savings = Saving.query.filter_by(user_id=user.id)

        return render_template('dashboard.html',
                                    curDate=today_localize.today().date(),
                                    user_id=user.id,
                                    username=user.username,
                                    totalAmount=formattedTotalAmount,
                                    spendAmount=formattedSpendAmount,
                                    spendAmountStatusColor=spendAmountStatusColor,
                                    availableAmount=formattedAvailableAmount,
                                    operationStatistics=operationStatistics,
                                    currencies=currencies,
                                    userCurrencies=userCurrencies,
                                    leftCurrencies=leftCurrencies,
                                    haveCurrencies=haveCurrencies,
                                    savings=savings,
                                    hideAmounts=userConfig.hide_amounts,
                                    operationTypes=operationTypes,
                                    operationTypeIcons=operationTypeIcons,
                                    operationTypeIconsColor=operationTypeIconsColor,
                                    operations=operations,
                                    form=filterForm,
                                    form2=newOperationForm,
                                    form3=editOperationForm,
                                    form4=userSettingsForm,
                                    form5=addCurrencyForm,
                                    form6=changeCurrencyForm)

    elif request.method == 'POST':
        filterForm = FiltersForm()

        # Set DataTypes to all the Selects of EveryForm in Dashboard View
        filterForm.month_id.choices = [(m.id, m.description) for m in Month.query.order_by('id')]
        filterForm.month_id.choices.insert(0, ('0', 'Todos'))

        year = today_localize.year
        yearList = list(range(year, year - 21, -1))
        filterForm.year_id.choices = [(index, description) for index, description in enumerate(yearList, start=0)]
        
        filterForm.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]
        filterForm.type_id.choices.insert(0, ('0', 'Todos'))

        userSettingsForm = UserSettingsForm()

        if filterForm.type_id.data != 0 and filterForm.month_id.data != 0:
            if not filterForm.is_submitted() or not filterForm.validate():
                flash('Los valores de los filtros son incorrectos', category="alert-danger")

        if userSettingsForm.is_submitted() and userSettingsForm.validate():
            # Get User Configuration
            userConfig = UserConfiguration.query.filter_by(user_id=userSettingsForm.user_id.data).first()

            # Update the fields with the current values
            userConfig.spend_limit = float(userSettingsForm.spend_limit.data.replace("$", "").replace(",", ""))
            userConfig.warning_percent = int(userSettingsForm.warning_percent.data)
            userConfig.hide_amounts = userSettingsForm.hide_amounts.data

            db.session.commit()
            flash('La configuración fue actualizada con éxito', category='alert-success')
        
        messages = json.dumps({'month_id': filterForm.month_id.data,'year_id': filterForm.year_id.data, 'type_id': filterForm.type_id.data})
        return redirect(url_for('main.dashboard', messages=messages))

@main.route('/home/dashboard/new_operation', methods=['POST'])
@login_required
def new_operation():
    # Obtain data from template
    formOperation = NewOperationForm()
    formOperation.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]
    
    userCurrencies = Saving.query.filter_by(user_id=formOperation.user_id.data).with_entities(Saving.currency_id)
    haveCurrencies = Currency.query.filter(Currency.id.in_(userCurrencies))
    formOperation.currency_id.choices = [(c.id, c.description) for c in haveCurrencies]

    if formOperation.validate():
        # Parse amount string to decimal
        convertedAmount = float(formOperation.amount.data.replace("$","").replace(",",""))
        if convertedAmount <= 0:
            flash('El gasto de la operación debe ser mayor a 0.', category="alert-danger")
            return redirect(url_for('main.dashboard'))
        
        # Search User Configuration to verify Spend Limit
        userConfig = UserConfiguration.query.filter_by(user_id=formOperation.user_id.data).first()

        # Set currency_id to null in case that is not type 17
        currencyId = None
        if (formOperation.type_id.data != 15 and formOperation.type_id != 17 and userConfig.spend_limit != 0 and convertedAmount > userConfig.spend_limit):
                flash('El gasto supera el límite establecido en la configuración.', category="alert-danger")
                return redirect(url_for('main.dashboard'))
        elif formOperation.type_id.data == 17:
            # Save Saving in DB
            saving = Saving.query.filter_by(user_id=formOperation.user_id.data, currency_id=formOperation.currency_id.data).first()

            saving.amount=saving.amount + convertedAmount
            db.session.commit()

            currencyId = formOperation.currency_id.data

        # Save operation in DB
        operation = Operation(description= formOperation.description.data, date=formOperation.date.data, amount=convertedAmount, type_id=formOperation.type_id.data, user_id=formOperation.user_id.data, currency_id=currencyId)
        
        db.session.add(operation)
        db.session.commit()
        
        flash('La operación fue creada con éxito!', category="alert-success")
        return redirect(url_for('main.dashboard'))

    flash('Hubo un problema al crear la operación', category="alert-danger")
    return redirect(url_for('main.dashboard', form2=formOperation, showNewModal=True))


@main.route('/home/dashboard/update_operation/<string:id>', methods=['POST'])
@login_required
def update_operation(id):
    editOperationForm = NewOperationForm()
    editOperationForm.type_id.choices = [(o.id, o.description) for o in OperationType.query.order_by('description')]

    userCurrencies = Saving.query.filter_by(user_id=editOperationForm.user_id.data).with_entities(Saving.currency_id)
    haveCurrencies = Currency.query.filter(Currency.id.in_(userCurrencies))
    editOperationForm.currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
    
    if editOperationForm.validate():
        # Parse amount string to decimal
        convertedAmount = float(editOperationForm.amount.data.replace("$","").replace(",",""))

        # Search User Configuration to verify Spend Limit
        userConfig = UserConfiguration.query.filter_by(user_id=editOperationForm.user_id.data).first()

        if userConfig.spend_limit != 0 and convertedAmount > userConfig.spend_limit:
                flash('El gasto supera el límite establecido en la configuración.', category="alert-danger")
                return redirect(url_for('main.dashboard'))
        else:
            # Search the edited operation from DB to update it
            edit_operation = Operation.query.filter_by(id=id).first()

            # Update the fields
            previousCurrencyType = -1
            previousCurrencyDesc = None
            previousAmount = edit_operation.amount
            edit_operation.description = editOperationForm.description.data
            edit_operation.date = editOperationForm.date.data
            edit_operation.amount = convertedAmount
            edit_operation.type_id = editOperationForm.type_id.data
            if editOperationForm.type_id.data == 17:
                previousCurrencyType = edit_operation.currency_id
                previousCurrencyDesc = Currency.query.filter_by(id=edit_operation.currency_id).first()
                edit_operation.currency_id = editOperationForm.currency_id.data
            
            
            if editOperationForm.type_id.data == 17:
                saving = Saving.query.filter_by(user_id=editOperationForm.user_id.data, currency_id=previousCurrencyType).first()
                if saving.amount - previousAmount >= 0:
                    saving.amount = saving.amount - previousAmount

                    saving = Saving.query.filter_by(user_id=editOperationForm.user_id.data, currency_id=editOperationForm.currency_id.data).first()
                    saving.amount = saving.amount + convertedAmount
                    db.session.commit()
                else:
                    flash("Ya no tienes ese monto en tu cuenta de ahorro en {0}, por lo que no se puede restar el dinero. Puedes ingresar más de forma manual y volver a intentarlo".format(previousCurrencyDesc.description), category="alert-danger")
                    return redirect(url_for('main.dashboard'))
            
            db.session.commit()
            flash('La operación fue actualizada con éxito', category='alert-success')
            return redirect(url_for('main.dashboard'))

    flash('Hubo un problema al actualizar la operación', category='alert-danger')
    return redirect(url_for('main.dashboard'))

@main.route('/home/dashboard/delete_operation/<string:id>', methods=['POST'])
@login_required
def delete_operation(id):
    # Detele operation from DB
    Operation.query.filter_by(id=id).delete()

    db.session.commit()
    flash('La operación fue eliminada con éxito', category='alert-success')
    return redirect(url_for('main.dashboard'))


@main.route('/home/dashboard/add_curency', methods=['POST'])
@login_required
def add_currency():
    addCurrencyForm = AddCurrencyForm()

    # Load left user currencies
    userCurrencies = Saving.query.filter_by(user_id=addCurrencyForm.user_id.data).with_entities(Saving.currency_id)
    leftCurrencies = Currency.query.filter(Currency.id.notin_(userCurrencies))
    addCurrencyForm.currency_id.choices = [(c.id, c.description) for c in leftCurrencies]

    if addCurrencyForm.validate():
        # Save saving in DB
        saving = Saving(user_id=addCurrencyForm.user_id.data, currency_id=addCurrencyForm.currency_id.data, amount=0)
        
        db.session.add(saving)
        db.session.commit()

        flash('La moneda fue agregada correctamente', category='alert-success')
        return redirect(url_for('main.dashboard'))
        
    flash('Hubo un problema al agregar la moneda', category="alert-danger")
    return redirect(url_for('main.dashboard'))

@main.route('/home/dashboard/exchange_curency', methods=['POST'])
@login_required
def exchange_currency():
    changeCurrencyForm = ChangeCurrencyForm()
    
    # load have user currencies
    userCurrencies = Saving.query.filter_by(user_id=changeCurrencyForm.user_id.data).with_entities(Saving.currency_id)
    haveCurrencies = Currency.query.filter(Currency.id.in_(userCurrencies))
    changeCurrencyForm.origin_currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
    changeCurrencyForm.destination_currency_id.choices = [(c.id, c.description) for c in haveCurrencies]
    haveCurrencies = haveCurrencies.all()

    if changeCurrencyForm.validate():
        originSaving = Saving.query.filter_by(user_id=changeCurrencyForm.user_id.data, currency_id=changeCurrencyForm.origin_currency_id.data).first()
        destinationSaving = Saving.query.filter_by(user_id=changeCurrencyForm.user_id.data, currency_id=changeCurrencyForm.destination_currency_id.data).first()
        
        originAmount = float(changeCurrencyForm.origin_amount.data.replace("$","").replace(",",""))
        
        if originSaving.amount - originAmount >= 0:
            originSaving.amount = originSaving.amount - originAmount
            print(changeCurrencyForm.total_amount.data)
            destinationSaving.amount = destinationSaving.amount + float(changeCurrencyForm.total_amount.data)

            db.session.commit()
            flash('Se han convertido {0} {1} a {2} {3} correctamente'.format(changeCurrencyForm.origin_amount.data, haveCurrencies[originSaving.currency_id -1].description, changeCurrencyForm.total_amount.data, haveCurrencies[destinationSaving.currency_id -1].description), category='alert-success')
            return redirect(url_for('main.dashboard'))
        else:
            flash("No tienes ese monto en tu cuenta de ahorro en {0}, por lo que no se puede intercambiar el dinero. Puedes ingresar más de forma manual y volver a intentarlo".format(haveCurrencies[originSaving.currency_id -1].description), category="alert-danger")
            return redirect(url_for('main.dashboard'))

    flash('Hubo un error al realizar la conversión de monedas', category='alert-danger')
    return redirect(url_for('main.dashboard'))

@main.route('/home/dashboard/delete_saving/<string:id>', methods=['POST'])
@login_required
def delete_saving(id):
    # Detele operation from DB
    Saving.query.filter_by(id=id).delete()

    db.session.commit()

    flash('La moneda fue eliminada con éxito', category='alert-success')
    return redirect(url_for('main.dashboard'))