from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from models import User,UserGroup,Expense
from pymongo.errors import DuplicateKeyError
app = Flask(__name__)
app.config['SECRET_KEY'] = 'QWERTY234565432POIUYR'
app.config['MONGO_URI'] = 'mongodb+srv://testsplitwiseapp:Z8HsGJKPnVfpdUIx@cluster0.ahnrles.mongodb.net/mydatabase?retryWrites=true&w=majority'
mongo = PyMongo(app)
mongo=mongo.db


def update_balances(expense, group_id):
    # Get the MongoDB collection for balances within the group
    balance_collection = mongo[f'balances_group_{group_id}']

    # Deduct the expense amount from the payer's balance
    payer_balance = balance_collection.find_one({'user_id': expense.payer})
    if payer_balance:
        payer_balance['balance'] -= expense.amount
        balance_collection.update_one({'user_id': expense.payer}, {'$set': {'balance': payer_balance['balance']}})
    else:
        # If payer's balance doesn't exist, create a new balance record
        balance_collection.insert_one({'user_id': expense.payer, 'balance': -expense.amount})

    if expense.expense_type == 'EQUAL':
        # Split the expense equally among participants
        for participant in expense.participants:
            if participant != expense.payer:
                participant_balance = balance_collection.find_one({'user_id': participant})
                if participant_balance:
                    participant_balance['balance'] += (expense.amount / (len(expense.participants) - 1))
                    balance_collection.update_one({'user_id': participant}, {'$set': {'balance': participant_balance['balance']}})
                else:
                    # If participant's balance doesn't exist, create a new balance record
                    balance_collection.insert_one({'user_id': participant, 'balance': (expense.amount / (len(expense.participants) - 1))})

    elif expense.expense_type == 'EXACT':
        # Split the expense based on exact amounts specified in shares
        for share in expense.shares:
            participant_balance = balance_collection.find_one({'user_id': share['user']})
            if participant_balance:
                participant_balance['balance'] += share['amount']
                balance_collection.update_one({'user_id': share['user']}, {'$set': {'balance': participant_balance['balance']}})
            else:
                # If participant's balance doesn't exist, create a new balance record
                balance_collection.insert_one({'user_id': share['user'], 'balance': share['amount']})

    elif expense.expense_type == 'PERCENT':
        # Split the expense based on percentages specified in shares
        for share in expense.shares:
            participant_balance = balance_collection.find_one({'user_id': share['user']})
            if participant_balance:
                participant_balance['balance'] += share['amount']
                balance_collection.update_one({'user_id': share['user']}, {'$set': {'balance': participant_balance['balance']}})
            else:
                # If participant's balance doesn't exist, create a new balance record
                balance_collection.insert_one({'user_id': share['user'], 'balance': share['amount']})

def generate_user_id():
    last_user = mongo.users.find_one(sort=[("userId", -1)])
    if last_user:
        last_user_id = last_user['userId']
        print("last user is",last_user_id)
        next_user_id = int(last_user_id[1:]) + 1
        print("last user is",next_user_id)
        
        print("last user found",next_user_id)
    else:
        next_user_id = 1
        print("no user found",next_user_id)
    print(next)
    return f'u{next_user_id}'  # Padded with zeros

@app.route('/users', methods=['POST'])
def create_user():
    # print(mongo)
    data = request.get_json()
    name = data['name']
    email = data['email']
    mobile = data['mobile']
    # return data
    user_id = generate_user_id()
    user_data = {
        'userId': user_id,
        'name': name,
        'email': email,
        'mobile': mobile
    }
    mongo.users.insert_one(user_data)
    return jsonify({'message': 'User created successfully'})

@app.route('/users/all', methods=['GET'])
def get_all_users():
    # Retrieve all users from the 'users' collection
    users_collection = mongo.users.find()
    
    # Convert user data to a list of dictionaries
    users_list = [{
        'user_id': user['userId'],
        'name': user['name'],
        'email': user['email'],
        'mobile': user['mobile']
    } for user in users_collection]

    return jsonify({'users': users_list})

@app.route('/groups', methods=['POST'])
def create_group():
    data = request.get_json()
    group_name = data.get('group_name')
    usernames = data.get('members')  
    # Get the user IDs for the provided usernames
    user_ids = []
    for username in usernames:
        user = mongo.users.find_one({'name': username})
        if user:
            user_ids.append(user['userId'])
        else:
            return jsonify({'error': f'User with username {username} not found'}, 404)
    # Get the last group ID and increment it by 1
    last_group_id = mongo.groups.find_one_and_update(
        {'_id': 'group_id_counter'},
        {'$inc': {'sequence_value': 1}},
        upsert=True,
        return_document=True
    )
    group_id = last_group_id['sequence_value']
    # Create a new group document with the provided data and user IDs
    group_data = {
        'group_id': group_id,
        'group_name': group_name,
        'members': user_ids  # Save the user IDs
    }
    try:
        # Save the group to a 'groups' collection in your MongoDB
        mongo.groups.insert_one(group_data)
    except DuplicateKeyError:
        # Handle the case where a group with the same ID already exists
        return jsonify({'error': 'Group with this ID already exists'})
    return jsonify({'message': 'User group created successfully', 'group_id': group_id})

@app.route('/groups/<group_id>/members', methods=['GET'])
def get_group_members(group_id):
    # Assuming you have a 'groups' collection with a 'members' field containing an array of group members
    group = mongo.groups.find_one({'group_id': int(group_id)})
    if group:
        members = group.get('members', [])
        return jsonify({'members': members})
    else:
        return jsonify({'message': 'Group not found'}, 404)

@app.route('/groups/<group_id>/add_user', methods=['POST'])
def add_user_to_group(group_id):
    data = request.get_json()
    user_id = data['user_id']  # The user ID to be added to the group
    # Check if the user exists
    user = mongo.users.find_one({'userId': user_id})
    if not user:
        return jsonify({'error': 'User not found'}, 404)
    # Check if the group exists
    group = mongo.groups.find_one({'group_id': int(group_id)})
    if not group:
        return jsonify({'error': 'Group not found'}, 404)
    # Check if the user is already a member of the group
    if user_id in group['members']:
        return jsonify({'message': 'User is already a member of the group'})
    # Add the user to the group
    group['members'].append(user_id)
    mongo.groups.update_one({'group_id': int(group_id)}, {'$set': {'members': group['members']}})
    return jsonify({'message': 'User added to the group successfully'})


@app.route('/expenses/equal/<group_id>', methods=['POST'])
def create_equal_expense(group_id):
    data = request.json
    payer = data['payer']
    amount = data['amount']
    participants = data['participants']
    split_amount = amount / len(participants)
    shares = [{'user': participant, 'amount': split_amount} for participant in participants]
    description = data['description']
    expense_type = 'EQUAL'
    expense = Expense(description, amount, payer, participants, expense_type, shares)
    update_balances(expense, group_id)
    # Save the expense to MongoDB in the group's expenses collection
    expenses_collection = mongo[f'expenses_group_{group_id}']
    expense_data = {
        'description': description,
        'amount': amount,
        'payer': payer,
        'participants': participants,
        'expense_type': expense_type,
        'shares': shares
    }
    expenses_collection.insert_one(expense_data)
    return jsonify({'message': 'Expense created successfully'})\

@app.route('/expenses/unequal/<group_id>', methods=['POST'])
def create_unequal_expense(group_id):
    data = request.json
    payer = data['payer']
    amount = data['amount']
    shares = data['shares']
    total_shares_amount = sum(share['amount'] for share in shares)
    if total_shares_amount != amount:
        return jsonify({'error': 'Total shares amount does not match the expense amount'})
    description = data['description']
    participants = [payer] + [share['user'] for share in shares]
    expense_type = 'EXACT'
    expense = Expense(description, amount, payer, participants, expense_type, shares)
    update_balances(expense, group_id)
    # Save the expense to MongoDB in the group's expenses collection
    expenses_collection = mongo[f'expenses_group_{group_id}']
    expense_data = {
        'description': description,
        'amount': amount,
        'payer': payer,
        'participants': participants,
        'expense_type': expense_type,
        'shares': shares
    }
    expenses_collection.insert_one(expense_data)
    return jsonify({'message': 'Expense created successfully'})


@app.route('/expenses/percentage/<group_id>', methods=['POST'])
def create_percentage_expense(group_id):
    data = request.json
    payer = data['payer']
    amount = data['amount']
    percentages = data['percentages']
    total_percent = sum(percentages)
    if total_percent != 100:
        return jsonify({'error': 'Percentages do not add up to 100%'})
    shares = [{'user': payer, 'amount': amount * percentages[0] / 100}]
    for i in range(1, len(percentages)):
        shares.append({'user': data['participants'][i], 'amount': amount * percentages[i] / 100})
    description = data['description']
    participants = [payer] + data['participants']
    expense_type = 'PERCENT'
    expense = Expense(description, amount, payer, participants, expense_type, shares)
    update_balances(expense, group_id)
    # Save the expense to MongoDB in the group's expenses collection
    expenses_collection = mongo[f'expenses_group_{group_id}']
    expense_data = {
        'description': description,
        'amount': amount,
        'payer': payer,
        'participants': participants,
        'expense_type': expense_type,
        'shares': shares
    }
    expenses_collection.insert_one(expense_data)
    return jsonify({'message': 'Expense created successfully'})


@app.route('/expenses/<group_id>', methods=['GET'])
def get_expenses(group_id):
    expenses_collection = mongo[f'expenses_group_{group_id}']
    expenses_cursor = expenses_collection.find()
    expenses_list = [{
            'description': expense['description'],
            'amount': expense['amount'],
            'payer': expense['payer'],
            'participants': expense['participants'],
            'expense_type': expense['expense_type'],
            'shares': expense['shares']
        } for expense in expenses_cursor]
    return jsonify({'expenses': expenses_list})

@app.route('/group/balances/<group_id>', methods=['GET'])
def get_group_balances(group_id):
    # Get the MongoDB collection for balances within the group
    balance_collection = mongo[f'balances_group_{group_id}']

    # Retrieve balances for all users in the group
    balances = {}
    for balance in balance_collection.find():
        user_id = balance['user_id']
        user_balance = balance['balance']
        balances[user_id] = user_balance

    # Calculate who owes how much to whom
    owes_to = {}
    owes_from = {}

    for user_id_1, balance_1 in balances.items():
        for user_id_2, balance_2 in balances.items():
            if user_id_1 != user_id_2:
                if balance_1 < 0 and balance_2 > 0:
                    # User 1 owes money to User 2
                    if user_id_1 in owes_to:
                        owes_to[user_id_1].append({"user_id": user_id_2, "amount": abs(balance_1)})
                    else:
                        owes_to[user_id_1] = [{"user_id": user_id_2, "amount": abs(balance_1)}]
                    # User 2 is owed money by User 1
                    if user_id_2 in owes_from:
                        owes_from[user_id_2].append({"user_id": user_id_1, "amount": abs(balance_1)})
                    else:
                        owes_from[user_id_2] = [{"user_id": user_id_1, "amount": abs(balance_1)}]

    result = {
        "owes_to": owes_to,
        "owes_from": owes_from
    }

    return jsonify(result)

@app.route('/group/owes/<group_id>', methods=['GET'])
def get_group_owes(group_id):
    # Get the MongoDB collection for balances within the group
    balance_collection = mongo[f'balances_group_{group_id}']

    # Retrieve balances for all users in the group
    balances = {}
    for balance in balance_collection.find():
        user_id = balance['user_id']
        user_balance = balance['balance']
        balances[user_id] = user_balance

    # Calculate who owes whom and the corresponding amounts
    owes = []

    for user_id_1, balance_1 in balances.items():
        for user_id_2, balance_2 in balances.items():
            if user_id_1 != user_id_2:
                if balance_1 < 0 and balance_2 > 0:
                    # User 1 owes money to User 2
                    owes.append({"from_user_id": user_id_1, "to_user_id": user_id_2, "amount": abs(balance_1)})

    return jsonify(owes)


@app.route('/balances/<group_id>', methods=['GET'])
def get_balances(group_id):
    # Calculate and retrieve balances within the specified group
    balance_collection = mongo[f'balances_group_{group_id}']
    # Convert balances to a dictionary
    balances = {}
    for balance in balance_collection.find():
        balances[balance['user_id']] = balance['balance']
    return jsonify(balances)

if __name__ == '__main__':
    app.run(debug=True)
