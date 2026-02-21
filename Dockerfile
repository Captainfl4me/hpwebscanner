FROM archlinux:latest

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm hplip sane wget && \
    pacman -Scc --noconfirm

RUN yes d | hp-plugin -i
