import sys
import argparse
import json
import maya.cmds as cmds
import maya.mel as mel
import maya.standalone
maya.standalone.initialize(name='python')


def polyreduce(input, output, config):
    obj = {}
    with open(config) as f:
        obj = json.load(f)

    reduction_ratio = float(obj['reduction_ratio'])
    keep_border = float(obj['keep_border'])
    keep_crease = float(obj['keep_crease'])
    keep_hardedge = float(obj['keep_hardedge'])
    keep_sharpness = float(obj['keep_sharpness'])
    keep_quad = float(obj['keep_quad'])
    symmetry = float(obj['symmetry'])
    mel.eval('loadPlugin fbxmaya;FBXImport -f "' + input + '";')
    for mesh in cmds.ls(o=True, typ='mesh'):
        # https://help.autodesk.com/cloudhelp/2019/CHS/Maya-Tech-Docs/CommandsPython/polyReduce.html
        cmds.polyReduce(
            mesh,
            version=1,
            # This flag specifies the termination condition
            # to use when reducing the mesh. Default is 0.
            # 0 Percentage
            # 1 Vertex count
            # 2 Triangle count
            # vertexCount=0,
            # percentage=95, # meaning 5% of the original mesh
            # triangleCount=1000,
            termination=0,
            percentage=reduction_ratio * 100,
            # If true, reduction will try to retain geometric borders
            # and the border of the selection. Default is true.
            keepBorder=True,
            # If keepBorder is on, this flag specifies the weight to
            # assign to borders. Setting this value to 0 will disable
            # border preservation and a value of 1 will exactly preserve
            # all border vertices which is useful for matching adjacent
            # meshes. Default is 0.5.
            keepBorderWeight=keep_border,
            # If true, reduction will try to retain crease edges. Default is true.
            keepCreaseEdge=True,
            # If keepCreaseEdge is on, this flag specifies the weight to
            # assign to crease edges. Setting this value to 0 will
            # disable crease edge preservation and a value of 1 will
            # exactly preserve all crease edges. Default is 0.5.
            keepCreaseEdgeWeight=keep_crease,
            # If true, reduction will try to retain hard edges. Default is true.
            keepHardEdge=True,
            # If keepHardEdge is on, this flag specifies the weight to
            # assign to hard edges. Setting this value to 0 will disable
            # hard edge preservation and a value of 1 will exactly preserve
            # all hard edges. Default is 0.5.
            keepHardEdgeWeight=keep_hardedge,
            # This flag guarantees that if the original geometry is
            # preserved, the new geometry will have the same location.
            # Default is false.
            preserveLocation=False,
            # This flag guarantees that the topological type will be
            # preserved during reduction. In particular, if the input
            # is manifold then the output will be manifold. This option
            # also prevents holes in the mesh from being closed off.
            # Default is true.
            preserveTopology=True,
            # Sharpness controls the balance between preserving
            # small, sharp details versus larger shapes. At
            # low values, details that are small relative to
            # the general shape of the object are more likely
            # to be collapsed. At high values, they are more
            # likely to be kept. Default is 0.
            sharpness=keep_sharpness,
            # This flag controls how much consideration is
            # given to preserving quad faces during reduction.
            # A higher weight means the reduction will try
            # harder to keep quad faces and avoid creation
            # of triangles. If the keepQuadsWeight flag is
            # set to 1.0 then a special quad reduction algorithm
            # is used that does a better job of preserving
            # quads. Howver, this special quad reduction
            # algorithm does not support symmetry so those
            # flags will be ignored when the keepQuadsWeight
            # flag is set to 1.0. Default is 0.
            keepQuadsWeight=keep_quad,
            # This flag controls whether symmetry is preserved during
            # the reduction. This flag only applies when the
            # keepQuadsWeight flag is less than 1.0. Default is 0.
            # 0 No symmetry preservation
            # 1 Automatic. Try to find suitable symmetry during reduction.
            # 2 Plane. Specify a symmetry plane to use during reduction.
            useVirtualSymmetry=1,
            # Tolerance to use when applying symmetry. For
            # each vertex of the mesh, we find its exact
            # symmetric point, then we look for the closest
            # vertex to the exact symmetry up to the tolerance
            # distance. Higher values risk finding more
            # spurious symmetries, lower values might miss
            # symmetries. The value is distance in object
            # space. This flag only applies when the
            # useVirtualSymmetry flag is not set to 0. Default is 0.
            symmetryTolerance=symmetry,
            # X/Y/Z/W value of the symmetry plane. This flag only applies
            # when the useVirtualSymmetry flag is set to 2. Default is 0.
            sx=0, sy=1, sz=0, sw=0)
        try:
            mel.eval('FBXExport -f "' + output + '";')
        except Exception:
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description='polyreduce')
    parser.add_argument('input', type=str,
                        help='path refers to reduction mesh file')
    parser.add_argument('output', type=str,
                        help='path refers to reduction config file')
    parser.add_argument('config', type=str,
                        help='path refers to reduction config file')
    args = parser.parse_args()
    polyreduce(args.input, args.output, args.config)


if __name__ == "__main__":
    main()
