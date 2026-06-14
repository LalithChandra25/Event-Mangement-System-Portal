
CREATE DATABASE eventdb;

USE eventdb;

CREATE TABLE users(
id INT AUTO_INCREMENT PRIMARY KEY,
username VARCHAR(50),
password VARCHAR(50)
);

CREATE TABLE events(
id INT AUTO_INCREMENT PRIMARY KEY,
event_name VARCHAR(100),
event_date DATE,
event_location VARCHAR(100)
);
 CREATE TABLE attendance(
id INT AUTO_INCREMENT PRIMARY KEY,
event_id INT,
person_name VARCHAR(100)
);
CREATE TABLE gallery(
id INT AUTO_INCREMENT PRIMARY KEY,
event_id INT,
image VARCHAR(200)
);