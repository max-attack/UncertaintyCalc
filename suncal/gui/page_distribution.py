''' GUI for exploring distributions and doing manual Monte Carlo '''

import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from .. import dist_explore
from .. import customdists
from .. import output
from .. import uparser
from . import gui_common
from . import gui_widgets


class DistEntry(QtWidgets.QWidget):
    ''' Widget showing one line in the distribution setup list

        Parameters
        ----------
        name: string
            Name/Expression for this distribution
        dist: stats.rv_continuous
            Stats distribution
    '''
    addDist = QtCore.pyqtSignal(object)  # emits DistEntry object
    remDist = QtCore.pyqtSignal(object)
    sampleDist = QtCore.pyqtSignal(str)  # emits name/expr of dist
    changeDist = QtCore.pyqtSignal(str)

    def __init__(self, name='', dist=customdists.normal(1), parent=None):
        super(DistEntry, self).__init__(parent)
        self.dist = dist
        self.btnAdd = QtWidgets.QToolButton()
        self.btnRem = QtWidgets.QToolButton()
        self.btnCustom = QtWidgets.QToolButton()
        self.btnSample = QtWidgets.QToolButton()
        self.btnAdd.setText('+')
        self.btnRem.setText(gui_common.CHR_ENDASH)
        self.btnCustom.setText('normal...')
        self.btnSample.setText('Sample')
        self.btnAdd.setToolTip('Insert distribution')
        self.btnRem.setToolTip('Remove distribution')
        self.btnCustom.setToolTip('Define distribution parameters')
        self.btnSample.setToolTip('Generate random samples')
        self.txtName = QtWidgets.QLineEdit(name)

        self.btnAdd.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.btnRem.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.btnCustom.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.btnSample.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        self.btnCustom.clicked.connect(self.editdist)
        self.btnAdd.clicked.connect(lambda y, x=self: self.addDist.emit(x))
        self.btnRem.clicked.connect(lambda y, x=self: self.remDist.emit(x))
        self.btnSample.clicked.connect(lambda x: self.sampleDist.emit(self.get_name()))
        self.txtName.editingFinished.connect(self.change_name)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.btnAdd)
        layout.addWidget(self.btnRem)
        layout.addWidget(self.txtName)
        layout.addWidget(self.btnCustom)
        layout.addWidget(self.btnSample)
        self.setLayout(layout)

    def editdist(self):
        ''' Show dialog for editing distribution parameters '''
        name = self.get_name()
        dlg = DistDialog(name, self.dist, parent=self)
        ok = dlg.exec()
        if ok:
            self.dist = dlg.get_dist()
            self.btnCustom.setText(self.dist.dist.name + '...')
            self.changeDist.emit(name)

    def change_name(self):
        ''' Name was changed. Check if it's an expression or base variable '''
        name = self.get_name()
        try:
            expr = uparser.check_expr(name)
        except ValueError:
            self.txtName.blockSignals(True)
            self.txtName.setText('ERROR')
            self.txtName.blockSignals(False)
        else:
            if hasattr(expr, 'is_symbol') and expr.is_symbol:
                self.btnCustom.setEnabled(True)  # Base variable, can customize
                self.btnCustom.setText(self.dist.dist.name + '...')
                self.btnSample.setText('Sample')
            else:
                self.btnCustom.setEnabled(False)
                self.btnCustom.setText('Monte Carlo')
                self.btnSample.setText('Calculate')
        self.changeDist.emit(name)

    def get_name(self):
        ''' Get name/expression for this distribution '''
        return self.txtName.text()


class DistDialog(QtWidgets.QDialog):
    ''' Dialog for editing distribution parameters '''
    def __init__(self, name, dist, parent=None):
        super(DistDialog, self).__init__(parent=parent)
        self.name = name
        self.dist = dist
        args = customdists.get_config(self.dist)
        self.table = gui_widgets.DistributionEditTable(args)
        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        self.btnBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        self.setWindowTitle('Configure Probability Distribution')
        self.setMaximumSize(600, 600)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.table, stretch=10)
        layout.addWidget(self.canvas, stretch=10)
        layout.addWidget(self.btnBox)
        self.setLayout(layout)

        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)
        self.table.changed.connect(self.replot)
        self.replot()

    def get_dist(self):
        ''' Get the distribution stats.rv_continuous '''
        return self.dist

    def replot(self):
        ''' Update the distribution and replot '''
        self.dist = self.table.statsdist
        mean = self.dist.mean()
        std = self.dist.std()
        xx = np.linspace(mean - 4*std, mean + 4*std, num=200)
        try:
            yy = self.dist.pdf(xx)
        except AttributeError:   # Discrete distribution has no pdf(). Approximate it.
            samples = self.dist.rvs(10000).astype(float)
            yy, xx = np.histogram(samples, bins=200)
            xx = xx[1:]

        self.fig.clf()
        ax = self.fig.add_subplot(1, 1, 1)
        ax.plot(xx, yy)
        ax.set_xlabel(output.format_math(self.name))
        self.fig.tight_layout()
        self.canvas.draw_idle()


class DistributionListWidget(QtWidgets.QWidget):
    ''' Widget for showing a list of distributions. Wrap this in a ScrollArea. '''
    sample = QtCore.pyqtSignal(str)
    changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(DistributionListWidget, self).__init__(parent=parent)
        self.pagelayout = QtWidgets.QVBoxLayout()
        self.setLayout(self.pagelayout)
        self.pagelayout.addStretch()  # Stretch is always last item in layout

    def addItem(self, name='', dist=customdists.normal(1), after=None):
        ''' Add a distribution to the list '''
        item = DistEntry(name, dist)
        item.addDist.connect(lambda x: self.addItem(after=x))
        item.remDist.connect(lambda x: self.remItem(item=x))
        item.changeDist.connect(self.changed)
        item.sampleDist.connect(self.sample)

        if after is not None:
            index = self.pagelayout.indexOf(after) + 1
        else:
            index = self.pagelayout.count() - 1
        self.pagelayout.insertWidget(index, item)
        self.changed.emit(name)

    def remItem(self, item=None):
        ''' Remove distribution '''
        self.pagelayout.removeWidget(item)
        item.setParent(None)
        name = item.txtName.text()
        if self.pagelayout.count() == 1:  # 1 because last item is stretch
            self.addItem()
        self.changed.emit(name)

    def clear(self):
        ''' Remove all items, but leave a blank one to edit. '''
        while self.pagelayout.count() > 0:
            item = self.pagelayout.itemAt(0).widget()
            self.pagelayout.removeWidget(item)
            if item:
                item.setParent(None)
        self.pagelayout.addStretch()
        self.addItem()

    def get_dists(self):
        ''' Return list of distribution name/expressions. '''
        dists = {}
        for i in range(self.pagelayout.count()-1):  # -1 because last layout item is a stretch
            item = self.pagelayout.itemAt(i).widget()
            name = item.get_name()
            if name != 'ERROR':
                dists[name] = item.dist
        return dists


class DistWidget(QtWidgets.QWidget):
    ''' Page widget for distribution explorer '''
    def __init__(self, item, parent=None):
        super(DistWidget, self).__init__(parent)
        assert isinstance(item, dist_explore.DistExplore)
        self.distexplore = item

        self.distlist = DistributionListWidget()
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidget(self.distlist)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumWidth(400)
        self.samples = QtWidgets.QLineEdit('10000')
        self.samples.setValidator(QtGui.QIntValidator(1, 10000000))
        self.samples.setMaximumWidth(300)
        self.samples.editingFinished.connect(lambda: self.distexplore.set_numsamples(int(self.samples.text())))

        self.cmbView = QtWidgets.QComboBox()
        self.cmbView.addItems(self.distexplore.samplevalues.keys())
        self.cmbFit = QtWidgets.QComboBox()
        dists = gui_common.settings.getDistributions()
        dists = [d for d in dists if hasattr(customdists.get_dist(d), 'fit')]
        self.cmbFit.addItems(['None'] + dists)
        self.chkConf = QtWidgets.QCheckBox('Show 95% Confidence')
        self.chkProbPlot = QtWidgets.QCheckBox('Show Probability Plot')
        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.txtOutput = gui_widgets.MarkdownTextEdit()

        llayout = QtWidgets.QVBoxLayout()
        llayout.addWidget(QtWidgets.QLabel('Input distributions and Monte Carlo expressions:'))
        llayout.addWidget(self.scroll)
        slayout = QtWidgets.QHBoxLayout()
        slayout.addWidget(QtWidgets.QLabel('Samples:'))
        slayout.addWidget(self.samples)
        llayout.addLayout(slayout)
        rlayout = QtWidgets.QVBoxLayout()
        clayout = QtWidgets.QHBoxLayout()
        clayout.addWidget(QtWidgets.QLabel('Output:'))
        clayout.addWidget(self.cmbView)
        clayout.addStretch()
        clayout.addWidget(QtWidgets.QLabel('Fit:'))
        clayout.addWidget(self.cmbFit)
        clayout.addWidget(self.chkConf)
        clayout.addWidget(self.chkProbPlot)
        rlayout.addLayout(clayout)
        rlayout.addWidget(self.canvas, stretch=10)
        rlayout.addWidget(self.toolbar)
        rlayout.addWidget(self.txtOutput, stretch=6)
        layout = QtWidgets.QHBoxLayout()
        layout.addLayout(llayout)
        layout.addLayout(rlayout)
        self.setLayout(layout)

        # Initialize
        if len(self.distexplore.dists) == 0:
            self.distlist.addItem('a')  # Make a new distribution named 'a'
            self.dist_changed()   # Save it
        else:
            for expr, dist in self.distexplore.dists.items():
                self.distlist.addItem(str(expr), dist)

        self.menu = QtWidgets.QMenu('Distributions')
        self.actSave = QtWidgets.QAction('Save report...', self)
        self.actClear = QtWidgets.QAction('Clear', self)
        self.menu.addAction(self.actClear)
        self.menu.addAction(self.actSave)
        self.actClear.triggered.connect(self.clear)
        self.actSave.triggered.connect(self.save_report)
        self.cmbView.currentIndexChanged.connect(self.changeview)
        self.cmbFit.currentIndexChanged.connect(self.changeview)
        self.chkProbPlot.stateChanged.connect(self.changeview)
        self.chkConf.stateChanged.connect(self.changeview)
        self.distlist.sample.connect(self.sample)
        self.distlist.changed.connect(self.dist_changed)

    def get_menu(self):
        ''' Get the menu for this widget '''
        return self.menu

    def clear(self):
        ''' Clear the distribution list '''
        self.distexplore.samplevalues = {}
        self.distlist.clear()
        self.cmbView.clear()

    def changeview(self):
        ''' Output view changed. Update plot and text report. '''
        name = self.cmbView.currentText()
        if name in self.distexplore.samplevalues:
            fitdist = self.cmbFit.currentText()
            fitdist = None if fitdist == 'None' else fitdist
            qq = self.chkProbPlot.isChecked()
            if fitdist is None and qq:
                fitdist = 'normal'

            self.distexplore.out.plot_hist(name, fig=self.fig, fitdist=fitdist, qqplot=qq, conf=self.chkConf.isChecked())
            self.txtOutput.setMarkdown(self.distexplore.out.report_single(name, **gui_common.get_rptargs()))
            self.fig.suptitle(output.format_math(name))
            self.canvas.draw_idle()
        else:
            self.txtOutput.setText('Sample a variable to see statistics.')

    def dist_changed(self, name=None):
        ''' Distribution changed, store to DistExplore object '''
        dists = self.distlist.get_dists()
        self.distexplore.dists = dists
        if name is not None:
            self.distexplore.samplevalues.pop(name, None)
        self.updatecmbView()
        self.changeview()

    def updatecmbView(self, name=None):
        ''' Add available (sampled) items to combo box and select name, if given '''
        self.cmbView.blockSignals(True)
        self.cmbView.clear()
        self.cmbView.addItems(list(self.distexplore.samplevalues.keys()))
        if name is not None:
            self.cmbView.setCurrentIndex(self.cmbView.findText(name))
        else:
            self.cmbView.setCurrentIndex(0)
        self.cmbView.blockSignals(False)

    def sample(self, name):
        ''' Sample the distribution '''
        try:
            self.distexplore.sample(name)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'Sampling', 'Undefined variable in expression {}'.format(name))
        self.updatecmbView(name=name)
        self.changeview()

    def get_report(self):
        ''' Get full report '''
        fitdist = self.cmbFit.currentText()
        fitdist = None if fitdist == 'None' else fitdist
        qq = self.chkProbPlot.isChecked()
        conf = self.chkConf.isChecked()
        return self.distexplore.get_output().report_all(fitdist=fitdist, conf=conf, qqplot=qq, **gui_common.get_rptargs())

    def save_report(self):
        ''' Save full report, asking user for settings/filename '''
        gui_widgets.savemarkdown(self.get_report())