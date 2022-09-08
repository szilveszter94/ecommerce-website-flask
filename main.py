import datetime
from email.message import EmailMessage
from flask import Flask, render_template, url_for, request, redirect, flash, abort, make_response
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from forms import *
from functools import wraps
from pathlib import Path
import pdfkit
import random
import smtplib
import stripe
from sqlalchemy.orm import relationship
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------- SET APPLICATION ------------------------------------------------------- #

# Set stripe api for card payment

stripe.api_key = 'YOUR STRIPE API'
YOUR_DOMAIN = 'http://192.168.1.202:5000'

# Set Flask application

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///website.db"
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'

# Set constants

my_email = "YOUR EMAIL"
my_password = "YOUR EMAIL PASSWORD"

# Set database and bootstrap

db = SQLAlchemy(app)
Bootstrap(app)

# Set login manager

login_manager = LoginManager()
login_manager.init_app(app)


# --------------------------------------------- SET DATABASE ---------------------------------------------------- #

# user database model
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    cart = relationship("Cart", back_populates="cart_owner")
    profile = relationship("Profile", back_populates="profile_owner")
    user_orders = relationship("OrderNumbers", back_populates="user_orders_owner")


# cart database model
class Cart(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    cart_owner = relationship("User", back_populates="cart")
    img_url1 = db.Column(db.String(250), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    product_price = db.Column(db.String, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_id = db.Column(db.String(250), nullable=False)


# user profile database model
class Profile(db.Model):
    __tablename__ = "profile"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    profile_owner = relationship("User", back_populates="profile")
    first_name = db.Column(db.String(250), nullable=True)
    last_name = db.Column(db.String(250), nullable=True)
    country = db.Column(db.String(250), nullable=True)
    company_name = db.Column(db.String(250), nullable=True)
    address = db.Column(db.String(250), nullable=True)
    city = db.Column(db.String(250), nullable=True)
    zip_code = db.Column(db.String(250), nullable=True)
    email = db.Column(db.String(250), nullable=True)
    phone_number = db.Column(db.String(250), nullable=True)


# products database model
class Products(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(250), unique=True, nullable=False)
    product_price = db.Column(db.String, nullable=False)
    category = db.Column(db.String(250), nullable=False)
    description = db.Column(db.String(250), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    img_url1 = db.Column(db.String(250), nullable=False)
    img_url2 = db.Column(db.String(250), nullable=False)
    img_url3 = db.Column(db.String(250), nullable=False)
    img_url4 = db.Column(db.String(250), nullable=False)
    price_id = db.Column(db.String(250), nullable=False)


# orders database model
class OrderNumbers(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_orders_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user_orders_owner = relationship("User", back_populates="user_orders")
    order_number = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(250), nullable=False)
    last_name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    phone_number = db.Column(db.String(250), nullable=False)
    country = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(250), nullable=False)
    payment = db.Column(db.String(250), nullable=False)
    price = db.Column(db.String(250), nullable=False)
    products_in_cart = db.Column(db.String(250), nullable=False)
    company = db.Column(db.String(250), nullable=True)
    street_address = db.Column(db.String(250), nullable=False)
    zip_code = db.Column(db.String(250), nullable=False)
    comment = db.Column(db.String(250), nullable=True)
    date = db.Column(db.String(250), nullable=False)


db.create_all()


# ------------------------------------ FUNCTIONS ---------------------------------------------------------------- #

# random order number generator
def order_number_generator():
    random_number = random.randint(10000, 99999999)
    orders = OrderNumbers.query.all()
    if len(orders) == 0:
        return random_number
    else:
        for i in orders:
            while random_number == i.order_number:
                random_number = random.randint(10000, 99999999)
            else:
                return random_number


# return sum of all products in the user cart
def cart_summary():
    user_id = 1
    try:
        user_id = current_user.id
    except AttributeError:
        pass
    cart_product = Cart.query.filter_by(owner_id=user_id)
    quantity = 0
    for i in cart_product:
        quantity += i.quantity
    return quantity


# return sum of price of all products in cart
def summary(cart_product):
    price = 0
    for i in cart_product:
        price += int(i.product_price.split('$')[1]) * i.quantity
    return price


# check if the product is in the cart
def check_cart_product(cart_products, cart_product_id):
    for i in cart_products:
        if i.id == cart_product_id:
            return i


# check if the same product is already is in the cart
def check_duplicated(cart_products, product_to_add):
    for i in cart_products:
        if i.product_name == product_to_add.product_name:
            return i


# format the path of the location of the product image
def path_format(form):
    path = 'product_img/'
    file_type = form.category.data
    directory_name = form.product_name.data
    charset = [' ', '-', '.']
    for i in charset:
        directory_name = directory_name.replace(i, "_")
    f1 = form.img_url1.data
    f2 = form.img_url2.data
    f3 = form.img_url3.data
    f4 = form.img_url4.data
    filename1 = secure_filename(f1.filename)
    filename2 = secure_filename(f2.filename)
    filename3 = secure_filename(f3.filename)
    filename4 = secure_filename(f4.filename)
    file_paths = []
    file1 = f'{path}{file_type}/{directory_name}/{filename1}'
    file2 = f'{path}{file_type}/{directory_name}/{filename2}'
    file3 = f'{path}{file_type}/{directory_name}/{filename3}'
    file4 = f'{path}{file_type}/{directory_name}/{filename4}'
    file_paths.append(file1)
    file_paths.append(file2)
    file_paths.append(file3)
    file_paths.append(file4)
    return file_paths


# check if the product is in stock
def check_product_in_stock(cart_item):
    product = Products.query.filter_by(product_name=cart_item.product_name).first()
    if product.quantity > cart_item.quantity:
        return True
    else:
        return False


# ----------------------------------------------- ROUTES ------------------------------------------------------- #

# set login manager route
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# admin only route manager
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if current_user.id != 1:
                return abort(403)
        except AttributeError:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


# the home route
@app.route("/")
def home():
    # render 9 products from all products
    all_products = Products.query.all()
    products_in_cart = cart_summary()
    length = len(all_products)
    random_products = random.sample(all_products, 9)
    return render_template("index.html", current_user=current_user,
                           products_in_cart=products_in_cart,
                           all_products=all_products,
                           length=length, random_products=random_products)


# the add route
@app.route('/add', methods=["POST", "GET"])
@admin_only
# you can add new product
def add():
    form = AddForm()
    if form.validate_on_submit():
        path = path_format(form)
        new_product = Products(
            product_name=form.product_name.data,
            product_price=form.product_price.data,
            img_url1=path[0],
            img_url2=path[1],
            img_url3=path[2],
            img_url4=path[3],
            category=form.category.data,
            description=form.description.data,
            quantity=form.quantity.data,
            price_id=form.price_id.data
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add.html", form=form, current_user=current_user)


# render cancel page
@app.route("/cancel")
def cancel():
    return render_template("cancel.html")


# render success page
@app.route("/success")
def success():
    return render_template("success.html")


# render delete page, only for admin
@app.route('/delete/<string:id>')
@admin_only
# delete the product based on id
def delete(id):
    product_id = id
    product_to_delete = Products.query.get(product_id)
    db.session.delete(product_to_delete)
    db.session.commit()
    return redirect(url_for('shop'))


# render modify page, only for admin
@app.route('/modify/<string:id>', methods=["POST", "GET"])
@admin_only
# modify the product based on id
def modify(id):
    form = EditForm()
    if form.validate_on_submit():
        product_to_update = Products.query.filter_by(id=id).first()
        product_to_update.product_name = form.product_name.data
        product_to_update.product_price = form.product_price.data
        product_to_update.description = form.description.data
        product_to_update.category = form.category.data
        product_to_update.img_url1 = form.img_url1.data
        product_to_update.img_url2 = form.img_url2.data
        product_to_update.img_url3 = form.img_url3.data
        product_to_update.img_url4 = form.img_url4.data
        product_to_update.quantity = form.quantity.data
        product_to_update.price_id = form.price_id.data
        db.session.commit()
        return redirect(url_for('home'))
    this_product = Products.query.filter_by(id=id).first()
    form.product_name.data = this_product.product_name
    form.product_price.data = this_product.product_price
    form.description.data = this_product.description
    form.category.data = this_product.category
    form.img_url1.data = this_product.img_url1
    form.img_url2.data = this_product.img_url2
    form.img_url3.data = this_product.img_url3
    form.img_url4.data = this_product.img_url4
    form.price_id.data = this_product.price_id
    form.quantity.data = this_product.quantity
    return render_template("modify.html", form=form, current_user=current_user)


# login or register route
@app.route('/login-register', methods=["POST", "GET"])
# check if email exist or not and redirect to the corresponding page
def login_register():
    form = LoginRegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        if User.query.filter_by(email=email).first():
            return redirect(url_for("login", id=email))
        else:
            return redirect(url_for("register", id=email))
    return render_template("login-register.html", form=form, current_user=current_user)


# login route
@app.route('/login/<string:id>', methods=["POST", "GET"])
def login(id):
    form = LoginForm()
    form.email.data = id
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        # check if email exist
        if User.query.filter_by(email=email).first():
            user = User.query.filter_by(email=email).first()
            # check the password
            if check_password_hash(user.password, password) and user.email == email:
                login_user(user)
                return redirect(url_for("home"))
            # message if the password is wrong
            else:
                flash('Password incorrect, please try again.')
                return redirect(url_for('login', id=email))
        # message if the email is wrong
        else:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
    return render_template("login.html", form=form, current_user=current_user)


# register route
@app.route("/register/<string:id>", methods=["POST", "GET"])
def register(id):
    form = RegisterForm()
    form.email.data = id
    if form.validate_on_submit():
        # check the password
        if form.password.data == form.password_check.data:
            # hash the password
            hash_and_salted_password = generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=8
            )
            # create new user
            new_user = User(
                email=form.email.data,
                password=hash_and_salted_password

            )

            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            new_profile = Profile(
                profile_owner=current_user,
                email=id,
                first_name='First Name',
                last_name='Last Name',
                country='Country',
                company_name='Company Name',
                address='Street Address',
                city='City',
                zip_code='ZIP Code',
                phone_number='Phone Number'
            )
            db.session.add(new_profile)
            db.session.commit()
            return redirect(url_for("home"))
        else:
            flash("The passwords do not match")
    return render_template("register.html", form=form, current_user=current_user)


# logout route
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# increase quantity route
@app.route("/plus_button/<string:id>")
def plus_button(id):
    cart_product_id = int(id)
    cart_products = Cart.query.filter_by(owner_id=current_user.id)
    cart_item = check_cart_product(cart_products, cart_product_id)
    # check if have more products in stock, and increase the quantity in the user cart
    if check_product_in_stock(cart_item):
        cart_item.quantity += 1
        db.session.commit()
        return redirect(url_for('user_cart', id=current_user.id))
    # message if not have more products
    else:
        flash("You've reached the maximum limit of stock")
        return redirect(url_for('user_cart', id=current_user.id))


# decrease quantity route
@app.route("/minus_button/<string:id>")
def minus_button(id):
    # decrease the quantity of the products in the user cart
    cart_product_id = int(id)
    cart_products = Cart.query.filter_by(owner_id=current_user.id)
    cart_item = check_cart_product(cart_products, cart_product_id)
    # check if the quantity is higher than 1, and then, decrease the quantity
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
    db.session.commit()
    return redirect(url_for('user_cart', id=current_user.id))


# add to cart route
@app.route("/add_to_cart/<string:id>")
def add_to_cart(id):
    product_id = id
    product_to_add = Products.query.get(product_id)
    cart_products = Cart.query.filter_by(owner_id=current_user.id)
    if check_duplicated(cart_products, product_to_add):
        duplicated_product = check_duplicated(cart_products, product_to_add)
        if product_to_add.quantity - duplicated_product.quantity > 0:
            duplicated_product.quantity += 1
            db.session.commit()
        else:
            flash("You've reached the maximum limit of stock")
            return redirect(url_for('shop', id=current_user.id))
    # add new product into the user cart
    else:
        new_product = Cart(
            cart_owner=current_user,
            img_url1=product_to_add.img_url1,
            product_price=product_to_add.product_price,
            product_name=product_to_add.product_name,
            price_id=product_to_add.price_id,
            quantity=1
        )
        db.session.add(new_product)
        db.session.commit()
    return redirect(url_for('shop', id=current_user.id))


# user cart route
@app.route("/user_cart/<string:id>")
def user_cart(id):
    user_id = id
    # show all products in the user cart
    cart_product = Cart.query.filter_by(owner_id=user_id)
    price = summary(cart_product)
    products_in_cart = cart_summary()
    return render_template("cart.html", current_user=current_user, cart_product=cart_product, price=price,
                           products_in_cart=products_in_cart)


# delete cart route
@app.route("/delete_cart_item/<string:id>")
def delete_cart(id):
    item_id = int(id)
    cart_product = Cart.query.filter_by(owner_id=current_user.id)
    # delete product in the user cart
    for i in cart_product:
        if i.id == item_id:
            db.session.delete(i)
            db.session.commit()
    return redirect(url_for('user_cart', id=current_user.id))


# delete order route, only for admin
@app.route("/delete_order/<string:id>")
@admin_only
# delete order
def delete_order(id):
    order_id = int(id)
    order = OrderNumbers.query.filter_by(id=order_id).first()
    name_quantity_pairs = []
    order_details = order.products_in_cart.split(',')
    # reset the quantity of all products from the deleted order
    for i in range(0, len(order_details), 2):
        name_quantity_pairs.append({'name': order_details[i],
                                    'quantity': order_details[i + 1].split(' ')[0]})
    for i in name_quantity_pairs:
        this_product = Products.query.filter_by(product_name=i['name']).first()
        this_product.quantity += int(i['quantity'])
        db.session.commit()
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('database'))


# show the user orders
@app.route("/user_orders")
def user_orders():
    order = OrderNumbers.query.filter_by(user_orders_id=current_user.id)
    return render_template('profile.html', order=order, user_orders=True)


# delete user, only for admin
@app.route("/delete_user/<string:id>")
@admin_only
# delete user from the database
def delete_user(id):
    user_id = int(id)
    if user_id > 1:
        user = User.query.filter_by(id=user_id).first()
        user_profile = Profile.query.filter_by(profile_id=user_id).first()
        db.session.delete(user)
        db.session.delete(user_profile)
        db.session.commit()
    return redirect(url_for('user_management'))


# show user cart products
@app.route("/cart")
def cart():
    return render_template("cart.html", current_user=current_user)


# show the orders database, only for admin
@app.route("/database", methods=["POST", "GET"])
@admin_only
def database():
    if request.method == 'POST':
        word = request.form.get('search')
        search = "%{0}%".format(word)
        filtered_orders = OrderNumbers.query.filter(or_(OrderNumbers.order_number.like(search),
                                                        OrderNumbers.id.like(search),
                                                        OrderNumbers.first_name.like(search),
                                                        OrderNumbers.last_name.like(search),
                                                        OrderNumbers.street_address.like(search),
                                                        OrderNumbers.city.like(search),
                                                        OrderNumbers.company.like(search),
                                                        OrderNumbers.zip_code.like(search),
                                                        OrderNumbers.email.like(search),
                                                        OrderNumbers.phone_number.like(search),
                                                        OrderNumbers.payment.like(search),
                                                        OrderNumbers.price.like(search),
                                                        OrderNumbers.comment.like(search),
                                                        OrderNumbers.products_in_cart.like(search),
                                                        OrderNumbers.date.like(search))).all()
        return render_template("database.html", orders=filtered_orders, current_user=current_user)
    orders = OrderNumbers.query.all()
    return render_template("database.html", orders=orders, current_user=current_user)


# show the user database
@app.route("/user_management", methods=["POST", "GET"])
@admin_only
def user_management():
    if request.method == 'POST':
        word = request.form.get('search')
        search = "%{0}%".format(word)
        print(search)
        filtered_orders = Profile.query.filter(or_(Profile.profile_id.like(search),
                                                   Profile.first_name.like(search),
                                                   Profile.last_name.like(search),
                                                   Profile.address.like(search),
                                                   Profile.city.like(search),
                                                   Profile.company_name.like(search),
                                                   Profile.zip_code.like(search),
                                                   Profile.email.like(search),
                                                   Profile.phone_number.like(search))).all()
        return render_template("database.html", um=True, users=filtered_orders, current_user=current_user)
    users = Profile.query.all()
    return render_template("database.html", um=True, users=users, current_user=current_user)


# the checkout route
@app.route("/checkout", methods=["POST", "GET"])
def checkout():
    user_id = 1
    products_in_cart = cart_summary()
    try:
        user_id = current_user.id
    except AttributeError:
        pass
    # search all products in the user cart
    cart_product = Cart.query.filter_by(owner_id=user_id)
    # search user profile
    address = Profile.query.filter_by(profile_id=user_id).first()
    # show the price of all products
    price = summary(cart_product)
    if request.method == 'POST':
        date = datetime.datetime.now()
        today = date.strftime('%Y-%m-%d')
        order_number = order_number_generator()
        user_id = current_user.id
        cart_product = Cart.query.filter_by(owner_id=user_id)
        products_in_stock = Products.query.all()
        product_list = []
        out_of_stock = False
        out_of_stock_list = []
        price_id_list = []
        for i in cart_product:
            product_list.append(i.product_name)
            product_list.append(f'{i.quantity} pcs ')
            price_id_list.append({'price': i.price_id, 'quantity': i.quantity})
            # check if all products are still in stock
            for y in products_in_stock:
                if y.product_name == i.product_name:
                    if y.quantity < 0:
                        out_of_stock = True
                        out_of_stock_list.append(y.product_name)
                    else:
                        y.quantity -= i.quantity
                        db.session.commit()
        # if all products are in stock, make order
        if not out_of_stock:
            listToStr = ','.join(map(str, product_list))
            price = summary(cart_product)
            quantity = cart_summary()
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            company = request.form.get('company')
            country = request.form.get('country')
            email = request.form.get('email')
            street_address = request.form.get('street_address')
            city = request.form.get('city')
            zipcode = request.form.get('zipcode')
            phone_number = request.form.get('phone_number')
            comment = request.form.get('comment')
            payment = request.form.get('payment')
            # send all data to the order summary html form
            x = render_template('order-summary.html', country=country,
                                payment=payment, last_name=last_name,
                                company=company, email=email,
                                street_address=street_address, city=city,
                                zipcode=zipcode, phone_number=phone_number,
                                comment=comment, first_name=first_name, current_user=current_user, price=price,
                                products_in_cart=quantity, cart_product=cart_product, order_number=order_number)
            # create pdf from html
            path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
            config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
            pdf = pdfkit.from_string(x, False, configuration=config)
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'inline; filename=report_001.pdf'
            filename = Path('metadata.pdf')
            filename.write_bytes(response.data)
            newMessage = EmailMessage()
            newMessage['Subject'] = f"Visszaigazoló e-mail #{order_number} számú megrendelés"
            newMessage['From'] = my_email
            newMessage['To'] = email
            # send a pdf attachment from the order for the user
            newMessage.set_content('A megrendelés visszaigazolásárol készült dokumentumot csatolva elküldtük Önnek.')
            files = ['metadata.pdf']
            for file in files:
                with open(file, 'rb') as f:
                    file_data = f.read()
                    file_name = f.name
                newMessage.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)
            with smtplib.SMTP("smtp.gmail.com", 587) as connection:
                connection.starttls()
                connection.login(user=my_email, password=my_password)
                connection.send_message(newMessage)
            # save the order to the database
            order_details = OrderNumbers(user_orders_id=current_user.id, order_number=order_number,
                                         first_name=first_name, last_name=last_name,
                                         email=email,
                                         phone_number=phone_number, country=country, city=city, payment=payment,
                                         price=price,
                                         products_in_cart=listToStr, company=company, zip_code=zipcode,
                                         street_address=street_address, date=today)
            db.session.add(order_details)
            for i in cart_product:
                db.session.delete(i)
            db.session.commit()
            if payment == 'PayPal or CreditCard':
                try:
                    # redirect to the stripe checkout page, if the user choose online payment
                    checkout_session = stripe.checkout.Session.create(
                        line_items=price_id_list,
                        mode='payment',
                        success_url=YOUR_DOMAIN + '/success',
                        cancel_url=YOUR_DOMAIN + '/cancel',
                    )
                except Exception as e:
                    return str(e)
                return redirect(checkout_session.url, code=303)
        else:
            # message if some products are out of stock
            flash("Some products are out of stock or we don`t have enough product.")
            for i in out_of_stock_list:
                flash(f'Product name: {i}')
            # redirect to the checkout page
            return redirect(url_for('checkout'))
        return render_template("checkout.html", current_user=current_user, price=price,
                               products_in_cart=products_in_cart, address=address)
    return render_template("checkout.html", address=address,
                           current_user=current_user,
                           price=price, products_in_cart=products_in_cart)


# product details page
@app.route("/product-details/<string:id>", methods=["POST", "GET"])
def product_details(id):
    # show the detailed page of the product
    products_in_cart = cart_summary()
    this_product = Products.query.filter_by(product_name=id).first()
    return render_template("product-details.html", product=this_product, current_user=current_user,
                           products_in_cart=products_in_cart)


# shop route
@app.route("/shop")
def shop():
    # show all products in the shop
    products_in_cart = cart_summary()
    products = Products.query.all()
    return render_template("shop.html", products=products, current_user=current_user, products_in_cart=products_in_cart)


# filter from category
@app.route("/shop/<string:id>")
def category(id):
    category = id
    products_in_cart = cart_summary()
    products = Products.query.filter_by(category=category)
    return render_template("shop.html", products=products, current_user=current_user, products_in_cart=products_in_cart)


# profile route
@app.route("/profile", methods=["POST", "GET"])
# show the user profile
def profile():
    products_in_cart = cart_summary()
    profile_details = Profile.query.filter_by(profile_id=current_user.id).first()
    return render_template("profile.html", profile_details=profile_details,
                           current_user=current_user, products_in_cart=products_in_cart)


# edit profile route
@app.route("/edit_profile", methods=["POST", "GET"])
# edit user profile
def edit_profile():
    if request.method == 'POST':
        profile_to_update = Profile.query.filter_by(profile_id=current_user.id).first()
        profile_to_update.first_name = request.form.get('first_name')
        profile_to_update.last_name = request.form.get('last_name')
        profile_to_update.country = request.form.get('country')
        profile_to_update.company_name = request.form.get('company')
        profile_to_update.address = request.form.get('street_address')
        profile_to_update.city = request.form.get('city')
        profile_to_update.zip_code = request.form.get('zipcode')
        profile_to_update.phone_number = request.form.get('phone_number')
        db.session.commit()
        return redirect(url_for('profile'))
    products_in_cart = cart_summary()
    return render_template("edit-profile.html",
                           current_user=current_user, products_in_cart=products_in_cart)


# start the app
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
