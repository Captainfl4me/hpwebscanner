FROM archlinux:latest

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm hplip && \
    pacman -Scc --noconfirm
