# -*- coding: utf-8 -*-

"""
Logger - Sistema de logging centralizado da EVA.
"""

import logging
import sys
from datetime import datetime


class Logger:
    """
    Logger singleton para a EVA.
    """
    
    _instance = None
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str = "EVA") -> logging.Logger:
        """
        Retorna uma instância do logger.
        
        Args:
            name: Nome do logger (padrão: "EVA")
        
        Returns:
            Logger configurado
        """
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)
            
            # Remove handlers duplicados
            if logger.hasHandlers():
                logger.handlers.clear()
            
            # Handler para console
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # Formato: HORA | NIVEL | NOME | MENSAGEM
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            cls._loggers[name] = logger
        
        return cls._loggers[name]
    
    @classmethod
    def set_level(cls, name: str, level: str) -> None:
        """
        Altera o nível de log de um logger.
        
        Args:
            name: Nome do logger
            level: Nível (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if name in cls._loggers:
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL
            }
            cls._loggers[name].setLevel(level_map.get(level.upper(), logging.INFO))