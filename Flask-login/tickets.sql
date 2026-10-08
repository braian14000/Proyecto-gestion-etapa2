-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 01-10-2026 a las 13:56:32
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

CREATE DATABASE IF NOT EXISTS `tickets`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
USE `tickets`;

--
-- Base de datos: `tickets`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tickets`
--

CREATE TABLE `tickets` (
  `id` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `legajo` varchar(50) NOT NULL,
  `email` varchar(150) NOT NULL,
  `prioridad` varchar(20) NOT NULL,
  `categoria` varchar(100) NOT NULL,
  `descripcion` text NOT NULL,
  `estado` varchar(20) DEFAULT 'Pendiente',
  `fecha` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `tickets`
--

INSERT INTO `tickets` (`id`, `nombre`, `legajo`, `email`, `prioridad`, `categoria`, `descripcion`, `estado`, `fecha`) VALUES
(6, 'valentina', '911593', 'igurivictoria@gmail.com', 'media', 'No puedo inscribirme a un evento', 'kkk', 'solucionado', '2026-09-24 13:57:13'),
(7, 'Victoria', '911593', 'igurivictoria@gmail.com', 'baja', 'No puedo ver mi código QR', 'yyyyyy', 'solucionado', '2026-09-29 12:12:10'),
(8, 'nacho', '911593', 'igurivictoria@gmail.com', 'alta', 'No recibí el correo con el QR', 'kkkkkkkkk', 'solucionado', '2026-09-29 12:13:59');

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `tickets`
--
ALTER TABLE `tickets`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `tickets`
--
ALTER TABLE `tickets`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
