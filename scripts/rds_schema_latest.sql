--
-- PostgreSQL database dump
--

\restrict TUXfTZNUzF8GqEOjuVTzuwZ8QxKjJ2R66hmBbxVback3GqfZMOj6DHSDZj1EHQH

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: attendancestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.attendancestatus AS ENUM (
    'indi',
    'bindi'
);


--
-- Name: notificationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.notificationstatus AS ENUM (
    'gonderildi',
    'hatali',
    'beklemede'
);


--
-- Name: notificationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.notificationtype AS ENUM (
    'eve_varis_eta',
    'evden_alim_eta',
    'okula_varis',
    'eve_birakildi',
    'genel'
);


--
-- Name: organizationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.organizationtype AS ENUM (
    'school',
    'transport_company'
);


--
-- Name: triptype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.triptype AS ENUM (
    'to_school',
    'from_school'
);


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'veli',
    'sofor',
    'admin',
    'super_admin'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: absences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.absences (
    id character varying NOT NULL,
    student_id character varying NOT NULL,
    parent_id character varying NOT NULL,
    absence_date date NOT NULL,
    reason text,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: attendance_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attendance_logs (
    id character varying NOT NULL,
    student_id character varying NOT NULL,
    driver_id character varying NOT NULL,
    bus_id character varying NOT NULL,
    trip_session_id character varying,
    status public.attendancestatus NOT NULL,
    latitude numeric(10,8) NOT NULL,
    longitude numeric(11,8) NOT NULL,
    log_time timestamp without time zone NOT NULL,
    recorded_at timestamp with time zone,
    idempotency_key character varying,
    reverted_at timestamp with time zone,
    reverted_by_driver_id character varying
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id character varying NOT NULL,
    user_id character varying,
    action character varying NOT NULL,
    endpoint character varying NOT NULL,
    details character varying,
    status_code integer NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);


--
-- Name: bus_locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bus_locations (
    id character varying NOT NULL,
    bus_id character varying NOT NULL,
    latitude numeric(10,8) NOT NULL,
    longitude numeric(11,8) NOT NULL,
    speed numeric,
    "timestamp" timestamp without time zone NOT NULL
);


--
-- Name: buses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.buses (
    id character varying NOT NULL,
    plate_number character varying NOT NULL,
    capacity integer NOT NULL,
    school_id character varying NOT NULL,
    current_driver_id character varying,
    organization_id character varying
);


--
-- Name: email_verification_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_verification_tokens (
    id character varying NOT NULL,
    user_id character varying NOT NULL,
    token_hash character varying(128) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    requested_ip character varying(64),
    requested_user_agent character varying(1024)
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id character varying NOT NULL,
    recipient_id character varying NOT NULL,
    student_id character varying,
    title character varying NOT NULL,
    message text NOT NULL,
    notification_type public.notificationtype NOT NULL,
    status public.notificationstatus NOT NULL,
    is_read boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id character varying NOT NULL,
    name character varying(255) NOT NULL,
    type public.organizationtype NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone
);


--
-- Name: parent_student_relations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parent_student_relations (
    id character varying NOT NULL,
    parent_id character varying NOT NULL,
    student_id character varying NOT NULL
);


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id character varying NOT NULL,
    user_id character varying NOT NULL,
    token_hash character varying(128) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    requested_ip character varying(64),
    requested_user_agent character varying(1024)
);


--
-- Name: school_company_contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.school_company_contracts (
    id character varying NOT NULL,
    school_org_id character varying NOT NULL,
    company_org_id character varying NOT NULL,
    start_date date NOT NULL,
    end_date date,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: schools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schools (
    id character varying NOT NULL,
    school_name character varying NOT NULL,
    school_address character varying NOT NULL,
    contact_person_id character varying NOT NULL,
    latitude double precision,
    longitude double precision,
    organization_id character varying
);


--
-- Name: student_bus_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_bus_assignments (
    id character varying NOT NULL,
    bus_id character varying NOT NULL,
    student_id character varying NOT NULL
);


--
-- Name: students; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.students (
    id character varying NOT NULL,
    full_name character varying NOT NULL,
    student_number character varying NOT NULL,
    school_id character varying,
    organization_id character varying,
    address character varying,
    latitude double precision,
    longitude double precision,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: token_blacklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_blacklist (
    token character varying NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: trip_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trip_sessions (
    id character varying NOT NULL,
    bus_id character varying NOT NULL,
    driver_id character varying,
    trip_type public.triptype NOT NULL,
    service_date date NOT NULL,
    started_at timestamp with time zone NOT NULL,
    last_activity_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone
);


--
-- Name: trip_student_states; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trip_student_states (
    id character varying NOT NULL,
    trip_session_id character varying NOT NULL,
    student_id character varying NOT NULL,
    last_status public.attendancestatus,
    last_log_id character varying,
    last_event_at timestamp with time zone,
    route_completed_at timestamp with time zone
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying NOT NULL,
    full_name character varying NOT NULL,
    email character varying NOT NULL,
    phone_number character varying NOT NULL,
    password_hash character varying NOT NULL,
    password_changed_at timestamp with time zone,
    is_email_verified boolean NOT NULL,
    email_verified_at timestamp with time zone,
    role public.userrole NOT NULL,
    fcm_token character varying,
    is_active boolean NOT NULL,
    organization_id character varying,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone
);


--
-- Name: absences absences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.absences
    ADD CONSTRAINT absences_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num);


--
-- Name: attendance_logs attendance_logs_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: attendance_logs attendance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: bus_locations bus_locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_locations
    ADD CONSTRAINT bus_locations_pkey PRIMARY KEY (id);


--
-- Name: buses buses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_pkey PRIMARY KEY (id);


--
-- Name: buses buses_plate_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_plate_number_key UNIQUE (plate_number);


--
-- Name: email_verification_tokens email_verification_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_verification_tokens
    ADD CONSTRAINT email_verification_tokens_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: parent_student_relations parent_student_relations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student_relations
    ADD CONSTRAINT parent_student_relations_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: school_company_contracts school_company_contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.school_company_contracts
    ADD CONSTRAINT school_company_contracts_pkey PRIMARY KEY (id);


--
-- Name: schools schools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schools
    ADD CONSTRAINT schools_pkey PRIMARY KEY (id);


--
-- Name: student_bus_assignments student_bus_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_bus_assignments
    ADD CONSTRAINT student_bus_assignments_pkey PRIMARY KEY (id);


--
-- Name: students students_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_pkey PRIMARY KEY (id);


--
-- Name: students students_student_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_student_number_key UNIQUE (student_number);


--
-- Name: token_blacklist token_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist
    ADD CONSTRAINT token_blacklist_pkey PRIMARY KEY (token);


--
-- Name: trip_sessions trip_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_sessions
    ADD CONSTRAINT trip_sessions_pkey PRIMARY KEY (id);


--
-- Name: trip_student_states trip_student_states_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_student_states
    ADD CONSTRAINT trip_student_states_pkey PRIMARY KEY (id);


--
-- Name: student_bus_assignments uq_bus_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_bus_assignments
    ADD CONSTRAINT uq_bus_student UNIQUE (bus_id, student_id);


--
-- Name: parent_student_relations uq_parent_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student_relations
    ADD CONSTRAINT uq_parent_student UNIQUE (parent_id, student_id);


--
-- Name: school_company_contracts uq_school_company_contract; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.school_company_contracts
    ADD CONSTRAINT uq_school_company_contract UNIQUE (school_org_id, company_org_id);


--
-- Name: absences uq_student_absence_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.absences
    ADD CONSTRAINT uq_student_absence_date UNIQUE (student_id, absence_date);


--
-- Name: student_bus_assignments uq_student_single_bus_assignment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_bus_assignments
    ADD CONSTRAINT uq_student_single_bus_assignment UNIQUE (student_id);


--
-- Name: trip_sessions uq_trip_session_bus_type_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_sessions
    ADD CONSTRAINT uq_trip_session_bus_type_date UNIQUE (bus_id, trip_type, service_date);


--
-- Name: trip_student_states uq_trip_session_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_student_states
    ADD CONSTRAINT uq_trip_session_student UNIQUE (trip_session_id, student_id);


--
-- Name: users users_phone_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_number_key UNIQUE (phone_number);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_absences_student_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_absences_student_date ON public.absences USING btree (student_id, absence_date);


--
-- Name: ix_attendance_logs_bus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_logs_bus_id ON public.attendance_logs USING btree (bus_id);


--
-- Name: ix_attendance_logs_student_id_log_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_logs_student_id_log_time ON public.attendance_logs USING btree (student_id, log_time);


--
-- Name: ix_attendance_logs_trip_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_logs_trip_session_id ON public.attendance_logs USING btree (trip_session_id);


--
-- Name: ix_bus_locations_bus_id_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bus_locations_bus_id_timestamp ON public.bus_locations USING btree (bus_id, "timestamp");


--
-- Name: ix_bus_locations_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bus_locations_timestamp ON public.bus_locations USING btree ("timestamp");


--
-- Name: ix_buses_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_buses_organization_id ON public.buses USING btree (organization_id);


--
-- Name: ix_buses_school_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_buses_school_id ON public.buses USING btree (school_id);


--
-- Name: ix_contracts_company_org_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_company_org_id ON public.school_company_contracts USING btree (company_org_id);


--
-- Name: ix_contracts_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_is_active ON public.school_company_contracts USING btree (is_active);


--
-- Name: ix_contracts_school_org_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_school_org_id ON public.school_company_contracts USING btree (school_org_id);


--
-- Name: ix_email_verification_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_email_verification_tokens_token_hash ON public.email_verification_tokens USING btree (token_hash);


--
-- Name: ix_email_verification_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_verification_tokens_user_id ON public.email_verification_tokens USING btree (user_id);


--
-- Name: ix_notifications_recipient_id_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_id_created_at ON public.notifications USING btree (recipient_id, created_at DESC);


--
-- Name: ix_notifications_recipient_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_unread ON public.notifications USING btree (recipient_id, is_read) WHERE (is_read = false);


--
-- Name: ix_organizations_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_name ON public.organizations USING btree (name);


--
-- Name: ix_organizations_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_type ON public.organizations USING btree (type);


--
-- Name: ix_parent_student_relations_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parent_student_relations_parent_id ON public.parent_student_relations USING btree (parent_id);


--
-- Name: ix_parent_student_relations_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parent_student_relations_student_id ON public.parent_student_relations USING btree (student_id);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_schools_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_schools_organization_id ON public.schools USING btree (organization_id);


--
-- Name: ix_student_bus_assignments_bus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_student_bus_assignments_bus_id ON public.student_bus_assignments USING btree (bus_id);


--
-- Name: ix_student_bus_assignments_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_student_bus_assignments_student_id ON public.student_bus_assignments USING btree (student_id);


--
-- Name: ix_students_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_students_organization_id ON public.students USING btree (organization_id);


--
-- Name: ix_trip_sessions_bus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trip_sessions_bus_id ON public.trip_sessions USING btree (bus_id);


--
-- Name: ix_trip_sessions_service_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trip_sessions_service_date ON public.trip_sessions USING btree (service_date);


--
-- Name: ix_trip_student_states_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trip_student_states_student_id ON public.trip_student_states USING btree (student_id);


--
-- Name: ix_trip_student_states_trip_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trip_student_states_trip_session_id ON public.trip_student_states USING btree (trip_session_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id_organization_id ON public.users USING btree (id, organization_id);


--
-- Name: ix_users_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_organization_id ON public.users USING btree (organization_id);


--
-- Name: absences absences_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.absences
    ADD CONSTRAINT absences_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: absences absences_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.absences
    ADD CONSTRAINT absences_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: attendance_logs attendance_logs_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE RESTRICT;


--
-- Name: attendance_logs attendance_logs_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: attendance_logs attendance_logs_reverted_by_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_reverted_by_driver_id_fkey FOREIGN KEY (reverted_by_driver_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: attendance_logs attendance_logs_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: attendance_logs attendance_logs_trip_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_trip_session_id_fkey FOREIGN KEY (trip_session_id) REFERENCES public.trip_sessions(id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: bus_locations bus_locations_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_locations
    ADD CONSTRAINT bus_locations_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE CASCADE;


--
-- Name: buses buses_current_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_current_driver_id_fkey FOREIGN KEY (current_driver_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: buses buses_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: buses buses_school_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_school_id_fkey FOREIGN KEY (school_id) REFERENCES public.schools(id) ON DELETE RESTRICT;


--
-- Name: email_verification_tokens email_verification_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_verification_tokens
    ADD CONSTRAINT email_verification_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE SET NULL;


--
-- Name: parent_student_relations parent_student_relations_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student_relations
    ADD CONSTRAINT parent_student_relations_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: parent_student_relations parent_student_relations_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student_relations
    ADD CONSTRAINT parent_student_relations_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: school_company_contracts school_company_contracts_company_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.school_company_contracts
    ADD CONSTRAINT school_company_contracts_company_org_id_fkey FOREIGN KEY (company_org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: school_company_contracts school_company_contracts_school_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.school_company_contracts
    ADD CONSTRAINT school_company_contracts_school_org_id_fkey FOREIGN KEY (school_org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: schools schools_contact_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schools
    ADD CONSTRAINT schools_contact_person_id_fkey FOREIGN KEY (contact_person_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: schools schools_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schools
    ADD CONSTRAINT schools_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: student_bus_assignments student_bus_assignments_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_bus_assignments
    ADD CONSTRAINT student_bus_assignments_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE CASCADE;


--
-- Name: student_bus_assignments student_bus_assignments_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_bus_assignments
    ADD CONSTRAINT student_bus_assignments_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: students students_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: students students_school_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_school_id_fkey FOREIGN KEY (school_id) REFERENCES public.schools(id) ON DELETE RESTRICT;


--
-- Name: trip_sessions trip_sessions_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_sessions
    ADD CONSTRAINT trip_sessions_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE CASCADE;


--
-- Name: trip_sessions trip_sessions_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_sessions
    ADD CONSTRAINT trip_sessions_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: trip_student_states trip_student_states_last_log_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_student_states
    ADD CONSTRAINT trip_student_states_last_log_id_fkey FOREIGN KEY (last_log_id) REFERENCES public.attendance_logs(id) ON DELETE SET NULL;


--
-- Name: trip_student_states trip_student_states_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_student_states
    ADD CONSTRAINT trip_student_states_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: trip_student_states trip_student_states_trip_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_student_states
    ADD CONSTRAINT trip_student_states_trip_session_id_fkey FOREIGN KEY (trip_session_id) REFERENCES public.trip_sessions(id) ON DELETE CASCADE;


--
-- Name: users users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

--
-- Name: alembic_version bootstrap row; Type: DATA; Schema: public; Owner: -
--

INSERT INTO public.alembic_version (version_num) VALUES ('q1r2s3t4u5v6');

\unrestrict TUXfTZNUzF8GqEOjuVTzuwZ8QxKjJ2R66hmBbxVback3GqfZMOj6DHSDZj1EHQH
