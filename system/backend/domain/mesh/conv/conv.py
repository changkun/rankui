import bpy
import sys


def args():
    """returns the input fbx file path and output obj file path.
    """
    argv = sys.argv
    argv = argv[argv.index("--") + 1:]  # get all args after "--"
    conv = argv[0]
    input = argv[1]
    output = argv[2]
    return conv, input, output


def init_scene():
    """init initializes an empty scene for subsequent operations.
    """
    bpy.ops.wm.read_homefile()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def fbx2obj(input: str, output: str):
    """fbx2obj merges all objects, and exports to an obj file.
    """
    bpy.ops.import_scene.fbx(filepath=input, axis_forward='-Z', axis_up='Y')

    scene = bpy.context.scene
    obs = []
    for ob in scene.objects:
        # whatever objects you want to join...
        if ob.type == 'MESH':
            obs.append(ob)
    ctx = bpy.context.copy()
    ctx['active_object'] = obs[0]
    ctx['selected_objects'] = obs
    ctx['selected_editable_objects'] = obs
    bpy.ops.object.join(ctx)

    bpy.ops.export_scene.obj(
        filepath=output, axis_forward='-Z', axis_up='Y', use_materials=False)


def obj2fbx(input: str, output: str):
    """obj2fbx merges all objects, and exports to an fbx file.
    """
    bpy.ops.import_scene.obj(filepath=input, axis_forward='-Z', axis_up='Y')

    scene = bpy.context.scene
    obs = []
    for ob in scene.objects:
        # whatever objects you want to join...
        if ob.type == 'MESH':
            obs.append(ob)
    ctx = bpy.context.copy()
    ctx['active_object'] = obs[0]
    ctx['selected_objects'] = obs
    ctx['selected_editable_objects'] = obs
    bpy.ops.object.join(ctx)

    bpy.ops.export_scene.fbx(filepath=output, axis_forward='-Z', axis_up='Y')


if __name__ == "__main__":
    conv, i, o = args()

    try:
        init_scene()
        if conv == 'fbx2obj':
            fbx2obj(i, o)
        elif conv == 'obj2fbx':
            obj2fbx(i, o)
        else:
            # raise exception
            raise Exception('invalid conversion type')
    except Exception as e:
        print('conversion failed: ', e)
