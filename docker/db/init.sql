-- Adda database initialization
-- Creates required roles and extensions

CREATE ROLE myuser WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS;
ALTER ROLE myuser WITH PASSWORD 'addapass';

CREATE EXTENSION IF NOT EXISTS plpython3u;

-- Set the search path for plpython3u
ALTER DATABASE mydb SET search_path TO public;
