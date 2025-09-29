FROM nvidia/cuda:12.3.0-devel-ubuntu22.04

RUN apt-get update && \
    apt-get install -y build-essential cmake gnuplot libboost-all-dev graphviz libyaml-cpp-dev git libspdlog-dev python3 python3-pip python3-venv sudo

WORKDIR /app

COPY . /app
WORKDIR /app/tools/split
RUN rm -rf build && mkdir build

WORKDIR /app/tools/split/build
RUN cmake .. && make

WORKDIR /app
RUN make

WORKDIR /app/scripts/experiments
RUN python3 -m venv .venv

RUN . .venv/bin/activate && pip install -r requirements.txt

WORKDIR /app

RUN echo "source /app/scripts/experiments/.venv/bin/activate" >> ~/.bashrc
RUN echo "source /app/scripts/experiments/experiment_commands.sh" >> ~/.bashrc
RUN echo "show_help" >> ~/.bashrc

CMD ["bash"]