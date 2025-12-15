📚 README - Iracrates Bus Booking System (IBBS)
🌍 Project Overview
Iracrates Bus Booking System (IBBS) is a modern, digital bus ticket booking platform designed specifically for Uganda's transportation needs. It transforms the traditional manual booking process into a seamless online experience, addressing key pain points in Uganda's bus transportation sector.

🚀 Live Demo
Main Site: your-username.github.io/ibbs-uganda

Admin Demo: your-username.github.io/ibbs-uganda/admin.html

🎯 Problem Statement
In Uganda, bus passengers still depend on outdated manual methods:

🏃‍♂️ Long queues at bus parks (Kampala, Lira, Gulu, Arua, Mbale, etc.)

🎫 Risk of losing paper tickets

❌ No real-time bus availability information

📈 Overbooking and seat confusion

💰 Lack of price transparency

📱 Limited digital booking options for upcountry buses

✨ Solution
IBBS provides a comprehensive digital solution where passengers can:

🔍 View available buses and routes

💺 Choose specific seats

🎫 Book tickets instantly

💳 Pay via Mobile Money (MTN/Airtel)

📱 Receive SMS/email confirmations

Bus operators can:

🚌 Manage fleets and schedules

📊 Track bookings and revenue

📈 Reduce human errors

🎯 Maximize profits

👥 Target Users
🧑‍🎓 Students - Affordable travel options

👨‍💼 Workers - Daily commuters

🧳 Travelers - Inter-city passengers

🚌 Bus Companies - Fleet operators

👨‍💼 Transport Managers - Route planners

🛠️ Admins - System operators

🛠️ Core Features (MVP)
1. User Registration & Login
📱 Phone number/email registration

🔐 Secure login system

👨‍💼 Admin login for operators

2. Bus Search & Booking
🔍 Search by route, date, passengers

👁️ View available seats in real-time

🎯 Seat selection with visual layout

📅 Date and time scheduling

3. Payment System (Uganda-Focused)
📲 MTN Mobile Money integration

📶 Airtel Money payment option

💳 Bank transfer (Flutterwave) support

🔒 Secure transaction processing

4. Booking Management
📋 Unique booking numbers

📱 SMS/email confirmations

🖨️ Printable tickets

📊 Booking history

5. Admin Dashboard
🚌 Add/update/delete buses

🗺️ Manage routes and schedules

👁️ View all bookings

💰 Generate financial reports

🎨 Technology Stack
Purpose	Technology
Frontend	HTML5, CSS3, JavaScript
Backend	FastAPI/Django
Database	MySQL (Schema ready)
Local Server	XAMPP/WAMP
Payment	Mobile Money API (Demo)
Hosting	GitHub Pages (Current)
📁 Project Structure
text
ibbs-uganda/
├── 📄 index.html              # Main landing page
├── 📄 bus_companies.html      # Bus partners listing
├── 📄 routes.html             # Available routes
├── 📄 my_bookings.html        # User bookings page
├── 📄 help.html               # Help & support
├── 📄 login.html              # Login/Registration
├── 📄 admin.html              # Admin dashboard
├── 📁 assets/
│   ├── 📁 css/                # Stylesheets
│   ├── 📁 js/                 # JavaScript files
│   └── 📁 images/             # Images & icons
└── 📄 README.md               # This file
🗄️ Database Schema
sql
-- Users table
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    phone VARCHAR(15),
    email VARCHAR(100),
    password VARCHAR(255)
);

-- Buses table  
CREATE TABLE buses (
    bus_id INT PRIMARY KEY AUTO_INCREMENT,
    plate_number VARCHAR(20),
    capacity INT,
    company_id INT
);

-- Routes table
CREATE TABLE routes (
    route_id INT PRIMARY KEY AUTO_INCREMENT,
    from_city VARCHAR(50),
    to_city VARCHAR(50),
    price DECIMAL(10,2),
    duration VARCHAR(50)
);

-- Bookings table
CREATE TABLE bookings (
    booking_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    route_id INT,
    seat_number VARCHAR(10),
    booking_date DATE,
    payment_status ENUM('pending', 'completed', 'failed')
);
🚀 Getting Started
Quick Start (GitHub Pages)
Fork this repository or download the files

Enable GitHub Pages:

Go to Repository Settings → Pages

Select main branch as source

Save changes

Access your site: https://your-username.github.io/ibbs-uganda

Local Development
Install XAMPP or any PHP server

Clone repository:

bash
git clone https://github.com/your-username/ibbs-uganda.git
Move files to htdocs folder

Start Apache & MySQL from XAMPP control panel

Access locally: http://localhost/ibbs-uganda

📱 User Flow
text
1. User opens website/app
2. Registers or logs in
3. Searches for route (From → To + Date)
4. Selects preferred bus
5. Chooses seat from layout
6. Makes Mobile Money payment
7. Receives booking confirmation
8. Boards bus on travel day
✅ Benefits
For Passengers	For Bus Companies
✅ Saves time	✅ Maximizes profits
✅ Reduces congestion	✅ Reduces overbooking
✅ Transparent pricing	✅ Real-time tracking
✅ Secure bookings	✅ Digital management
✅ Easy planning	✅ Error reduction
🔮 Future Enhancements
🛰️ GPS tracking of buses

📱 Android/iOS app versions

🎫 QR-code tickets for boarding

👨‍✈️ Driver communication panel

💰 Discount & promo codes

🌍 Multi-language support (English & Luo)

👥 Contributing
Fork the repository

Create a feature branch (git checkout -b feature/AmazingFeature)

Commit your changes (git commit -m 'Add some AmazingFeature')

Push to the branch (git push origin feature/AmazingFeature)

Open a Pull Request

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

🆘 Support
📧 Email: support@ibbs.ug

📞 Phone: +256 700 123 456

🐛 Report Issues

🙏 Acknowledgments
Uganda Transport Association

All bus company partners

Student travelers community

Web Technologies class resources# IBBS-UG
Main Progect
