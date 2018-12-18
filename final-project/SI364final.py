import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, TextAreaField, IntegerField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json

from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

############################
# Application configurations
############################
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hard to guess string from si364'
## TODO 364: Create a database in postgresql in the code line below, and fill in your app's database URI. It should be of the format: postgresql://localhost/YOUR_DATABASE_NAME

## Your final Postgres database should be your uniqname, plus HW5, e.g. "jczettaHW5" or "maupandeHW5"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://jacobkreinik@localhost/jkreinikSI364Final" # TODO 364: You should edit this to correspond to the database name YOURUNIQNAMEHW4db and create the database of that name (with whatever your uniqname is; for example, my database would be jczettaHW4db). You may also need to edit the database URL further if your computer requires a password for you to run this.
## Provided:
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

##################
### App setup ####
##################
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager



########################
######## Models ########
########################


## Association Tables


recipe_to_list = db.Table('recipe_to_list', db.Column('recipe_id', db.Integer, db.ForeignKey('recipes.id')), db.Column('list_id', db.Integer, db.ForeignKey('recipe_lists.id')))


search_recipes = db.Table('search', db.Column('recipe_id', db.Integer, db.ForeignKey('recipes.id')), db.Column('search_term', db.String(32), db.ForeignKey('search_terms.term')))

## db Tables

class User(UserMixin, db.Model):
	__tablename__ = "users"
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(255), unique=True, index=True)
	email = db.Column(db.String(64), unique=True, index=True)
	password_hash = db.Column(db.String(128))
	recipe_list = db.relationship('RecipeLists', backref='User')


	@property
	def password(self):
		raise AttributeError('password is not a readable attribute')

	@password.setter
	def password(self, password):
		self.password_hash = generate_password_hash(password)

	def verify_password(self, password):
		return check_password_hash(self.password_hash, password)

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id)) # returns User object or None


class Recipe(db.Model):
	__tablename__='recipes'
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(64))
	ingredients = db.Column(db.String())
	def __repr__(self):
		return "Title:{}, Ingredients:{}".format(self.title,self.ingredients)


class RecipeLists(db.Model):
	__tablename__='recipe_lists'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(255))
	user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
	recipes = db.relationship('Recipe', secondary=recipe_to_list, backref=db.backref('recipe_lists', lazy='dynamic'), lazy='dynamic')


class SearchTerm(db.Model):
    __tablename__ = 'search_terms'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(32), unique=True)
    recipes = db.relationship('Recipe', secondary=search_recipes, backref=db.backref('search_terms', lazy='dynamic'), lazy='dynamic')
    def __repr__(self):
        return "{}".format(self.term)



########################
######## Forms #########
########################

class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')
    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')


class LoginForm(FlaskForm):
	email = StringField('Email', validators=[Required(), Length(1,64), Email()])
	password = PasswordField('Password', validators=[Required()])
	remember_me = BooleanField('Keep me logged in')
	submit = SubmitField('Log In')


class RecipeSearchForm(FlaskForm):
    search = StringField("Enter a key word to search for recipes", validators=[Required()])
    submit = SubmitField('Submit')

    def validate_search(self, field):
        numbers = ['0','1', '2', '3', '4', '5','6','7','8','9']
        for num in self.search.data:
            if num in numbers:
                raise ValidationError("Your search term may not contain numbers.")



class RecipeListForm(FlaskForm):
    name = StringField('What is the name of this recipe list',validators=[Required()])
    recipe_picks = SelectMultipleField('Recipes to include')
    submit = SubmitField("Create Recipe List")

class StartsWithForm(FlaskForm):
    letter = StringField('Enter only the FIRST LETTER (UPPERCASE) of recipes that you want to see', validators = [Required()])
    submit = SubmitField('Submit')


class UpdateButtonForm(FlaskForm):
	update = SubmitField('Update Recipe Name')

class UpdateNameForm(FlaskForm):
    name = StringField('Enter the new name for this recipe list', validators=[Required()])
    update = SubmitField('Update')

    def validate_name(self, field):
        if len(self.name.data.split(' ')) > 1: 
            raise ValidationError('Invalid recipe list name! list name must one word')


class DeleteButtonForm (FlaskForm):
	delete = SubmitField('Delete')



########################
### Helper functions ###
########################


def recipe_api_call(search):
	recipe_baseurl = 'http://www.recipepuppy.com/api/?'
	recipe_fullurl = requests.get(recipe_baseurl, params = {'q': search})
	result = json.loads(recipe_fullurl.text) 
	return result


def get_recipe_data(recipe_dict):
	data = []
	recipe = recipe_dict['results']
	for main in recipe:
		title = main['title']
		ingredients = main['ingredients']
		title_ingredients = (title, ingredients)
		data.append(title_ingredients)

	return data

def get_recipe_by_id(id):
	rec = Recipe.query.filter_by(id=id).first()
	return rec



def get_or_create_recipe(db_session, title, ingredients):
	recipe = db_session.query(Recipe).filter_by(title=title).first()
	if recipe:
		return recipe
	else:
		recipe = Recipe(title=title, ingredients=ingredients)
		db_session.add(recipe)
		db_session.commit()
		return recipe



def get_or_create_search_term(db_session, term, gif_list = []):
    search_term = db_session.query(SearchTerm).filter_by(term=term).first()
    if search_term:
        print("Found term")
        return search_term
    else:
        print ("Added term")
        search_term = SearchTerm(term=term)
        api_call = recipe_api_call(term)
        search = get_recipe_data(api_call)
        for x in search:
            recipe = get_or_create_recipe(db_session, title = x[0], ingredients = x[1])
            search_term.recipes.append(recipe)
        db_session.add(search_term)
        db_session.commit()
        return search_term



def get_or_create_recipe_lst(db_session, name, current_user, recipe_list):
    collection = RecipeLists.query.filter_by(name=name, user_id=current_user.id).first()
    if collection:
        return collection
    else:
        collection = RecipeLists(name=name, user_id=current_user.id, recipes=[])
        for x in recipe_list:
            collection.recipes.append(x)
        db_session.add(collection)
        db_session.commit()
        return collection




########################
#### View functions ####
########################

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500



@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))


@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))

    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('register.html', form=form)



@app.route('/', methods=['GET', 'POST'])
def index():
    form = RecipeSearchForm()
    if request.method == "POST" and form.validate_on_submit():
        search_term = get_or_create_search_term(db.session, term=form.search.data)
        return redirect(url_for('search_results', search_term=form.search.data))
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('index.html', form=form)



@app.route('/recipe_searched/<search_term>')
def search_results(search_term):
    term = SearchTerm.query.filter_by(term=search_term).first()
    relevant_recipes = term.recipes.all()
    return render_template('searched_recipes.html',recipes=relevant_recipes,term=term)




@app.route('/search_terms')
def search_terms():
    all_terms = SearchTerm.query.all()
    return render_template('search_terms.html', all_terms=all_terms)



@app.route('/all_recipes')
def all_recipes():
    recipes = Recipe.query.all()
    return render_template('all_recipes.html',all_recipes=recipes)


@app.route('/create_recipes_list',methods=["GET","POST"])
@login_required
def create_recipe_list():
    form = RecipeListForm()
    recipes = Recipe.query.all()
    choices = [(x.id, x.title) for x in recipes]
    form.recipe_picks.choices = choices
    if request.method == "POST":
        recipes_selected = form.recipe_picks.data
        recipe_objects = [get_recipe_by_id(int(id)) for id in recipes_selected]
        get_or_create_recipe_lst(db.session, name=form.name.data, current_user=current_user, recipe_list=recipe_objects)
        print("List created")
        return redirect(url_for('lists'))
    else:
        return render_template('create_recipe_list.html', form=form)


@app.route('/lists',methods=["GET","POST"])
@login_required
def lists():
    form = DeleteButtonForm()
    form2 = UpdateButtonForm()
    lists = RecipeLists.query.filter_by(user_id=current_user.id).all()
    return render_template('lists.html', lists=lists, form=form, form2=form2)



@app.route('/list/<id_num>')
def single_list(id_num):
    id_num = int(id_num)
    lst = RecipeLists.query.filter_by(id=id_num).first()
    recipes = lst.recipes.all()
    return render_template('list.html',lst=lst, recipes=recipes)


@app.route('/delete/<lst>',methods=["GET","POST"])
def delete(lst):
    current_lst = RecipeLists.query.filter_by(name=lst).first()
    db.session.delete(current_lst)
    db.session.commit()
    flash('The Recipe List {} has been deleted'.format(current_lst.name))
    return redirect(url_for('lists'))


@app.route('/update/<name>',methods=["GET","POST"])
def update(name):
    form = UpdateNameForm()
    if form.validate_on_submit():
        update_name = form.name.data
        current = RecipeLists.query.filter_by(name = name).first()
        current.name = update_name
        db.session.commit()

        flash ('The name of the list {} has been changed'.format(name))
        return redirect(url_for('lists'))
    else: 
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('update_item.html', form = form, name=name)

@app.route('/starting_letter_entry',methods=["GET","POST"])
def starting_letter_entry():
    form = StartsWithForm()
    if form.validate_on_submit() and request.method == 'GET':
        return redirect(url_for('starting_letter'))
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
    return render_template('start_entry.html', form = form)


@app.route('/letter',methods=["GET"])
def starting_letter():
    start = request.args.get('letter')
    first_letter = Recipe.query.filter(Recipe.title.startswith(start)).all()
    recipe_letter = []
    for x in first_letter:
        recipe_name = x.title
        recipe_letter.append(recipe_name)

    return render_template('recipe_letter.html', recipe_lst=recipe_letter, letter = start)



if __name__ == "__main__":
	db.create_all()
	manager.run()
