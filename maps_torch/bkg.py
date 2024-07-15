'''
Copyright (c) 2024, UChicago Argonne, LLC. All rights reserved.

Copyright 2024. UChicago Argonne, LLC. This software was produced
under U.S. Government contract DE-AC02-06CH11357 for Argonne National
Laboratory (ANL), which is operated by UChicago Argonne, LLC for the
U.S. Department of Energy. The U.S. Government has rights to use,
reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR
UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR
ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is
modified to produce derivative works, such modified software should
be clearly marked, so as not to confuse it with the version available
from ANL.

Additionally, redistribution and use in source and binary forms, with
or without modification, are permitted provided that the following
conditions are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in
      the documentation and/or other materials provided with the
      distribution.

    * Neither the name of UChicago Argonne, LLC, Argonne National
      Laboratory, ANL, the U.S. Government, nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago
Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
'''

### Initial Author <2024>: Xiangyu Yin

import torch
import numpy as np
from torchaudio.functional import convolve

from maps_torch.constant import M_SQRT2

def snip_op(background, current_width, max_of_xmin, min_of_xmax, device):
    lo_index = torch.minimum(
        torch.maximum(
            torch.arange(background.shape[-1], device=device).expand(background.shape)
            - current_width,
            torch.tensor(max_of_xmin, device=device),
        ),
        torch.tensor(min_of_xmax, device=device),
    ).to(torch.int64)
    hi_index = torch.maximum(
        torch.minimum(
            torch.arange(background.shape[-1], device=device).expand(background.shape)
            + current_width,
            torch.tensor(min_of_xmax, device=device),
        ),
        torch.tensor(max_of_xmin, device=device),
    ).to(torch.int64)
    return torch.minimum(
        (
            torch.gather(background, -1, lo_index)
            + torch.gather(background, -1, hi_index)
        )
        / 2,
        background,
    )


def snip_bkg(
    spec,
    er,
    e_offset,
    e_slope,
    e_quad,
    snip_width,
    boxcar_size=5,
    extra_info=False,
    device="cpu",
):
    xmin, xmax = er[0], er[1]
    energy = torch.arange(spec.shape[-1], device=device).expand(spec.shape)
    energy = e_offset + (energy * e_slope) + (energy**2 * e_quad)
    tmp = (e_offset / 2.3548) ** 2 + energy * 2.96 * e_slope
    tmp = torch.maximum(tmp, torch.zeros_like(tmp, device=device))
    background = convolve(
        spec,
        torch.tensor(
            np.expand_dims(
                np.array([1 / boxcar_size] * boxcar_size),
                axis=list(range(spec.ndim))[:-1],
            ),
            dtype=torch.float,
            device=device,
        ),
        mode="same",
    )
    if extra_info:
        bkgs = [background]
    current_width = snip_width * 2.35 * torch.sqrt(tmp) / e_slope
    background = torch.log(torch.log(background + 1) + 1)
    if extra_info:
        bkgs.append(background)
    max_of_xmin = max(xmin, 0)
    min_of_xmax = min(xmax, spec.shape[-1] - 1)
    for _ in range(2):
        background = snip_op(
            background, current_width, max_of_xmin, min_of_xmax, device=device
        )
        if extra_info:
            bkgs.append(background)
    while torch.max(current_width).item() >= 0.5:
        background = snip_op(
            background, current_width, max_of_xmin, min_of_xmax, device=device
        )
        if extra_info:
            bkgs.append(background)
        current_width = current_width / M_SQRT2
    background = torch.exp(torch.exp(background) - 1) - 1
    background = torch.nan_to_num(background)
    if extra_info:
        bkgs.append(background)
        return bkgs
    else:
        return background