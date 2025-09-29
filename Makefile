CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -pedantic -O3 -fopenmp
INCLUDES = -Iinclude -Ilib/x86-simd-sort

ifdef OPENMP_QS_x86_SIMD
    CXXFLAGS += -DXSS_USE_OPENMP
endif

ifdef QX_x86_SIMD_AVX512
    CXXFLAGS += -mavx512f -mavx512dq -mavx512vl
else
    CXXFLAGS += -mavx2
endif

TARGET = sort
SRCDIR = src
OBJDIR = build
BINPATH = $(OBJDIR)/$(TARGET)
COPY_DEST = tools/split/minibenchmarks/openmp

SOURCES = $(SRCDIR)/main.cpp
OBJECTS = $(OBJDIR)/main.o

all: $(BINPATH) copy

$(BINPATH): $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

copy: $(BINPATH)
	@if [ -d $(COPY_DEST) ]; then \
		cp $(BINPATH) $(COPY_DEST)/$(TARGET); \
	else \
		echo "Directory $(COPY_DEST) does not exist. Skipping copy."; \
	fi

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(OBJDIR)/%.o: $(SRCDIR)/%.cpp | $(OBJDIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

clean:
	rm -rf $(OBJDIR) $(TARGET) $(COPY_DEST)/$(TARGET)

.PHONY: all clean copy