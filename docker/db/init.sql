-- Adda database initialization
-- Creates required roles and extensions

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'myuser') THEN
        CREATE ROLE myuser WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS;
    END IF;
END
$$;
ALTER ROLE myuser WITH PASSWORD 'addapass';

CREATE EXTENSION IF NOT EXISTS plpython3u;

-- Set the search path for plpython3u
ALTER DATABASE mydb SET search_path TO public;
