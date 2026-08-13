# ALICE -- Adaptive Local Interface for Cohabitant Euthenics

## Project description

Embodied AI research platform combining perception, learned behavior, voice, a physical puppet, haptic interaction, and monitoring interfaces.

## Architecture

Python services coordinate state, vision, audio, logic, modes, and hardware; `brain/` contains training/inference; `dashboard/` observes the system; `Haptix/` is the gesture-driven haptic client; configuration and tests support operation.

## Technology

Python • PyTorch • React • WebSockets • Computer Vision

## Run locally

Install `requirements.txt`, configure `alice.yaml`, then run `python main.py`.

## Repository guide

The implementation is organized so that entry points remain thin and domain-specific logic stays in the modules named above. Configuration, assets, and deployment files are kept separate from application code. Review the source tree before changing behavior, and keep secrets in local environment files rather than committing them.
