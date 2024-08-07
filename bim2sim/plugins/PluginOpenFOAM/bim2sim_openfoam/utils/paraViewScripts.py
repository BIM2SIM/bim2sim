from paraview.simple import *

"""
A collection of paraView scripts for plotting different aspects of a 
simulated OpenFOAM case. 
!Can only be run inside paraView!
"""


def differenceSlice(case1: str, case2: str, var: str):
    """
    Calculates the mean-squared error between 2 OpenFOAM cases of the
    same geometry by taking a slice of the x-y-plane along the center of the
    space.
    case 1 and case2 must be paths to the OpenFOAM base directory containing
    the controlDict. Coloring is automatically scaled to a very small range
    and might need adjustment. var refers to the quantity to investigate and
    must be either T, U, U_X, U_Y, U_Z, AoA, Co, G, p, p_rgh or yPlus.
    """
    paraview.simple._DisableFirstRenderCameraReset()
    renderView1 = GetActiveViewOrCreate('RenderView')
    materialLibrary1 = GetMaterialLibrary()

    file1 = case1 + '/system/controlDict'
    file2 = case2 + '/system/controlDict'
    difference_variable = var  # T, U_X, U_Y, U_Z
    # difference_variable = 'U'  # for magnitude

    # create a new 'Open FOAM Reader'
    controlDict1 = OpenFOAMReader(registrationName='controlDict1', FileName=file1)
    controlDict1Display = Show(controlDict1, renderView1, 'UnstructuredGridRepresentation')
    controlDict1Display.Representation = 'Surface'
    controlDict1Display.SetScalarBarVisibility(renderView1, True)

    # create a new 'Slice'
    slice1 = Slice(registrationName='Slice1', Input=controlDict1)
    slice1Display = Show(slice1, renderView1, 'GeometryRepresentation')
    slice1Display.Representation = 'Surface'
    slice1Display.SetScalarBarVisibility(renderView1, True)

    # create a new 'Open FOAM Reader'
    controlDict = OpenFOAMReader(registrationName='controlDict', FileName=file2)
    controlDictDisplay = Show(controlDict, renderView1, 'UnstructuredGridRepresentation')
    controlDictDisplay.Representation = 'Surface'
    controlDictDisplay.SetScalarBarVisibility(renderView1, True)


    # create a new 'Slice'
    slice2 = Slice(registrationName='Slice2', Input=controlDict)
    slice2Display = Show(slice2, renderView1, 'GeometryRepresentation')
    slice2Display.Representation = 'Surface'
    slice2Display.SetScalarBarVisibility(renderView1, True)


    # set active source
    renameArrays1 = RenameArrays(registrationName='RenameArrays1', Input=slice1)
    renameArrays1.PointArrays = ['AoA', 'AoA_1', 'Co', 'Co_1', 'G', 'G_1', 'T',
                                 'T_1', 'U', 'U_1', 'a', 'a', 'alphat',
                                 'alphat', 'k', 'k', 'nut', 'nut', 'omega',
                                 'omega', 'p', 'p_1', 'p_rgh', 'p_rgh_1', 'qr',
                                 'qr', 'wallHeatFlux', 'wallHeatFlux', 'yPlus',
                                 'yPlus_1']
    renameArrays1Display = Show(renameArrays1, renderView1, 'GeometryRepresentation')
    renameArrays1Display.Representation = 'Surface'
    renameArrays1Display.SetScalarBarVisibility(renderView1, True)

    # create a new 'RenameArrays'
    renameArrays2 = RenameArrays(registrationName='RenameArrays2', Input=slice2)
    renameArrays2.PointArrays = ['AoA', 'AoA_2', 'Co', 'Co_2', 'G', 'G_2', 'T',
                                 'T_2', 'U', 'U_2', 'a', 'a', 'alphat',
                                 'alphat', 'k', 'k', 'nut', 'nut', 'omega',
                                 'omega', 'p', 'p_2', 'p_rgh', 'p_rgh_2', 'qr',
                                 'qr_2', 'wallHeatFlux', 'wallHeatFlux',
                                 'yPlus', 'yPlus_2']
    renameArrays2Display = Show(renameArrays2, renderView1, 'GeometryRepresentation')
    renameArrays2Display.Representation = 'Surface'
    renameArrays2Display.SetScalarBarVisibility(renderView1, True)


    # create a new 'Resample With Dataset'
    resampleWithDataset1 = ResampleWithDataset(registrationName='ResampleWithDataset1', SourceDataArrays=renameArrays2,
        DestinationMesh=renameArrays1)
    resampleWithDataset1.PassPointArrays = 1
    resampleWithDataset1Display = Show(resampleWithDataset1, renderView1, 'GeometryRepresentation')
    resampleWithDataset1Display.Representation = 'Surface'

    var1 = difference_variable + '_1'
    var2 = difference_variable + '_2'
    result_var = 'MSE(' + difference_variable + ')'
    # create a new 'Calculator'
    calculator1 = Calculator(registrationName='MSE-Calc',
                             Input=resampleWithDataset1)
    if difference_variable == 'U':
        calculator1.ResultArrayName = result_var + ' (mag)'
        calculator1.Function = 'sqrt((U_1_X - U_2_X)^2 + (U_1_Y - U_2_Y)^2 + (' \
                               'U_1_Z - U_2_Z)^2)'
    else:
        calculator1.ResultArrayName = result_var
        calculator1.Function = 'sqrt((' + var1 + '-' + var2 + ')^2)'
    calculator1Display = Show(calculator1, renderView1, 'GeometryRepresentation')
    calculator1Display.Representation = 'Surface'
    calculator1Display.SetScalarBarVisibility(renderView1, True)

    Hide(controlDict1, renderView1)
    Hide(controlDict, renderView1)
    Hide(slice1, renderView1)
    Hide(slice2, renderView1)
    Hide(renameArrays1, renderView1)
    Hide(renameArrays2, renderView1)
    Hide(resampleWithDataset1, renderView1)

    # get color transfer function/color map for 'T_diff'
    # get 2D transfer function for 'Result'
    resultTF2D = GetTransferFunction2D(result_var)
    resultTF2D.ScalarRangeInitialized = 1
    resultTF2D.Range = [0.0, 5.0, 0.0, 1.0]

    # get color transfer function/color map for 'Result'
    resultLUT = GetColorTransferFunction(result_var)
    resultLUT.TransferFunction2D = resultTF2D
    resultLUT.RGBPoints = [0.0, 0.231373, 0.298039, 0.752941, 1.5, 0.865003, 0.865003, 0.865003, 3.0, 0.705882, 0.0156863, 0.14902]
    resultLUT.ScalarRangeInitialized = 1.0

    # Apply a preset using its name. Note this may not work as expected when presets have duplicate names.
    resultLUT.ApplyPreset('Rainbow Desaturated', True)

    # get opacity transfer function/opacity map for 'Result'
    resultPWF = GetOpacityTransferFunction(result_var)
    resultPWF.Points = [0.0, 0.0, 0.5, 0.0, 3.0, 1.0, 0.5, 0.0]
    resultPWF.ScalarRangeInitialized = 1
    resultLUT.RescaleTransferFunction(0.0, 5.0)
    resultPWF.RescaleTransferFunction(0.0, 5.0)
    resultTF2D.RescaleTransferFunction(0.0, 5.0, 0.0, 1.0)
    renderView1 = GetActiveViewOrCreate('RenderView')

    # get layout
    layout1 = GetLayout()
    layout1.SetSize(1124, 789)
    renderView1.InteractionMode = '2D'
    renderView1.CameraPosition = [14.478500080108644, 7.84499979019165, 1.348009467124939]
    renderView1.CameraFocalPoint = [2.049999952316284, 7.84499979019165, 1.348009467124939]
    renderView1.CameraViewUp = [0.0, 0.0, 1.0]
    renderView1.CameraParallelScale = 1.8950963928630833

    file_name = difference_variable + '_Difference.png'
    SaveScreenshot(file_name)